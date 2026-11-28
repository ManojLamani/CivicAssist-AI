import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_auth_settings
from app.models import LoginSession, RefreshToken, User
from app.sessions import rotate_session, start_session


def log_in(client):
    account = {"email": "refresh@example.com", "password": "long-test-password"}
    response = client.post("/api/v1/auth/register", json=account | {"full_name": "Citizen"})
    assert response.status_code == 201
    response = client.post("/api/v1/auth/login", json=account)
    assert response.status_code == 200
    return response.json()


def current_user(client, tokens):
    return client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )


def test_refresh_rotates_and_only_stores_hashes(auth_client):
    client, connection = auth_client
    original = log_in(client)
    stored_hash = connection.scalar(select(RefreshToken.token_hash))
    assert stored_hash == hashlib.sha256(original["refresh_token"].encode()).hexdigest()
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    rotated = response.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert current_user(client, rotated).status_code == 200
    assert current_user(client, original).status_code == 200
    assert (
        connection.scalar(
            select(RefreshToken.used_at).where(RefreshToken.token_hash == stored_hash)
        )
        is not None
    )
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert again.status_code == 200


def test_refresh_replay_revokes_entire_login(auth_client):
    client, _ = auth_client
    original = log_in(client)
    rotated = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    ).json()
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
        ).status_code
        == 401
    )
    assert current_user(client, original).status_code == 401
    assert current_user(client, rotated).status_code == 401


def test_logout_is_idempotent_and_does_not_revoke_other_logins(auth_client):
    client, _ = auth_client
    first = log_in(client)
    second = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "long-test-password"},
    ).json()
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]}
        )
        assert response.status_code == 204
        assert response.content == b""
    assert current_user(client, first).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
        ).status_code
        == 401
    )
    assert current_user(client, second).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
        ).status_code
        == 200
    )


def test_expired_session_cannot_refresh_or_access_user(auth_client):
    client, connection = auth_client
    tokens = log_in(client)
    connection.execute(
        update(LoginSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert current_user(client, tokens).status_code == 401


def test_deleted_user_loses_tokens(auth_client):
    client, connection = auth_client
    tokens = log_in(client)
    connection.execute(delete(User))
    assert connection.scalar(select(RefreshToken.token_hash)) is None
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert current_user(client, tokens).status_code == 401


def test_expired_access_token_can_refresh_and_logout(auth_client):
    client, _ = auth_client
    original = log_in(client)
    secret = get_auth_settings().jwt_secret.get_secret_value()
    claims = jwt.decode(
        original["access_token"], secret, algorithms=["HS256"], audience="civicassist-api"
    )
    claims["exp"] = 1
    original["access_token"] = jwt.encode(claims, secret, algorithm="HS256")
    assert current_user(client, original).status_code == 401
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert rotated.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": original["refresh_token"]}
        ).status_code
        == 204
    )
    assert current_user(client, rotated.json()).status_code == 401


@pytest.mark.parametrize("token", ["not-a-token", secrets.token_urlsafe(48)])
def test_unknown_tokens_cannot_refresh_and_logout_is_safe(auth_client, token):
    client, _ = auth_client
    active = log_in(client)
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": token}).status_code == 204
    assert current_user(client, active).status_code == 200


@pytest.mark.parametrize("body", [{}, {"refresh_token": ""}, {"refresh_token": "x" * 129}])
def test_refresh_validation_does_not_echo_secrets(auth_client, body):
    client, _ = auth_client
    response = client.post("/api/v1/auth/refresh", json=body)
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])


def test_simultaneous_refresh_attempts_revoke_replayed_session(committed_database):
    with Session(committed_database) as session:
        user = User(email="race@example.com", full_name="Test", password_hash="unused-test-hash")
        session.add(user)
        session.flush()
        login_session, token = start_session(session, user.id)
        session_id = login_session.id
    barrier = Barrier(2)

    def rotate():
        with Session(committed_database) as session:
            barrier.wait(timeout=10)
            try:
                rotate_session(session, token)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: rotate(), range(2)))
    assert sorted(results) == [200, 401]
    with Session(committed_database) as session:
        assert session.get(LoginSession, session_id).revoked_at is not None
