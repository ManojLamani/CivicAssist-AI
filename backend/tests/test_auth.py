from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, select, update

from app.config import AuthSettings, get_auth_settings
from app.main import app
from app.models import LoginSession, User
from app.security import password_hash

ACCOUNT = {"email": "citizen@example.com", "password": "long-test-password", "full_name": "Citizen"}


def test_registration_login_and_current_user(auth_client):
    client, connection = auth_client
    response = client.post(
        "/api/v1/auth/register", json=ACCOUNT | {"email": " Citizen@EXAMPLE.com "}
    )
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "email", "full_name", "role_name"}
    assert user["email"] == ACCOUNT["email"]
    assert user["role_name"] == "citizen"
    stored_hash = connection.scalar(select(User.password_hash))
    assert stored_hash.startswith("$argon2id$")
    assert password_hash.verify(ACCOUNT["password"], stored_hash)
    credentials = {"email": "CITIZEN@example.com", "password": ACCOUNT["password"]}
    token = client.post("/api/v1/auth/login", json=credentials)
    assert token.status_code == 200
    assert token.json()["expires_in"] == 900
    assert token.headers["cache-control"] == "no-store"
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json() == user
    # Role information is read from the database, not a stale token claim.
    connection.execute(update(User).values(role_name="administrator"))
    assert client.get("/api/v1/auth/me", headers=headers).json()["role_name"] == "administrator"
    connection.execute(delete(User))
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_duplicate_registration(auth_client):
    client, _ = auth_client
    assert client.post("/api/v1/auth/register", json=ACCOUNT).status_code == 201
    assert client.post("/api/v1/auth/register", json=ACCOUNT).status_code == 409
    # The failed transaction must not poison subsequent requests.
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"role_name": "administrator"},
        {"role": "administrator"},
        {"password": "short"},
        {"password": "x" * 129},
        {"email": "invalid"},
        {"full_name": "   "},
    ],
)
def test_invalid_registration_cannot_create_user(auth_client, changes):
    client, connection = auth_client
    response = client.post("/api/v1/auth/register", json=ACCOUNT | changes)
    assert response.status_code == 422
    assert ACCOUNT["password"] not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert connection.scalar(select(User.id)) is None


def test_login_errors_do_not_reveal_account_existence(auth_client):
    client, _ = auth_client
    client.post("/api/v1/auth/register", json=ACCOUNT)
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": ACCOUNT["email"], "password": "wrong-password"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong-password"}
    )
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json() == {"detail": "Invalid credentials"}
    assert unknown.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"iss": "other-app"},
        {"aud": "other-app"},
        {"type": "refresh"},
        {"sub": "not-a-uuid"},
        {"sub": str(uuid4())},
        {"exp": None},
        {"sid": str(uuid4())},
        {"sid": "invalid"},
    ],
)
def test_invalid_tokens_are_rejected(auth_client, changes):
    client, connection = auth_client
    response = client.post("/api/v1/auth/register", json=ACCOUNT)
    client.post(
        "/api/v1/auth/login", json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]}
    )
    now = datetime.now(UTC)
    claims = {
        "sub": response.json()["id"],
        "sid": str(connection.scalar(select(LoginSession.id))),
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": "civicassist",
        "aud": "civicassist-api",
        "type": "access",
    } | changes
    if claims["exp"] is None:
        del claims["exp"]
    token = jwt.encode(claims, get_auth_settings().jwt_secret.get_secret_value(), algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic dGVzdA=="])
def test_missing_or_malformed_credentials(auth_client, authorization):
    client, _ = auth_client
    headers = {"Authorization": authorization} if authorization else {}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_bad_signature_is_rejected(auth_client):
    client, _ = auth_client
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=15)},
        "different-test-only-signing-secret-32-chars",
        algorithm="HS256",
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_signing_secret_is_required(monkeypatch):
    with pytest.raises(ValidationError):
        AuthSettings(_env_file=None, jwt_secret="short")
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ValidationError):
        AuthSettings(_env_file=None)


def test_browser_auth_preflight():
    response = TestClient(app).options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
