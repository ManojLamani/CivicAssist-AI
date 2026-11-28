from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.models import Complaint, User


def login(client, email="citizen@example.com"):
    account = {"email": email, "password": "long-test-password"}
    user = client.post("/api/v1/auth/register", json=account | {"full_name": "Citizen"}).json()
    tokens = client.post("/api/v1/auth/login", json=account).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}, user, tokens


@pytest.fixture
def report():
    return {
        "submission_id": str(uuid4()),
        "title": "Damaged road surface",
        "description": "A broken road surface needs inspection.",
        "category": "roads",
        "location": "Test street near the public park",
    }


def test_submission_is_persisted_owned_and_retry_safe(auth_client, report):
    client, connection = auth_client
    headers, user, _ = login(client)
    response = client.post("/api/v1/complaints", json=report, headers=headers)
    assert response.status_code == 201
    receipt = response.json()
    assert set(receipt) == {
        "id",
        "title",
        "description",
        "category",
        "location",
        "status",
        "created_at",
    }
    assert receipt["status"] == "submitted"
    stored = connection.execute(select(Complaint.__table__)).mappings().one()
    assert stored["user_id"] == UUID(user["id"])
    assert str(stored["id"]) == receipt["id"]
    assert stored["created_at"].tzinfo is not None
    assert response.headers["cache-control"] == "no-store"
    retry = client.post("/api/v1/complaints", json=report, headers=headers)
    assert retry.status_code == 200
    assert retry.json() == receipt
    assert connection.scalar(select(func.count()).select_from(Complaint)) == 1
    conflict = client.post(
        "/api/v1/complaints", json=report | {"title": "Another report"}, headers=headers
    )
    assert conflict.status_code == 409
    assert connection.scalar(select(Complaint.title)) == report["title"]


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"title": "x" * 161},
        {"description": "short"},
        {"description": "x" * 5001},
        {"category": "invalid"},
        {"location": " "},
        {"location": "x" * 501},
        {"submission_id": "invalid"},
        {"status": "resolved"},
        {"user_id": str(uuid4())},
    ],
)
def test_invalid_submissions_are_rejected(auth_client, report, changes):
    client, connection = auth_client
    headers, _, _ = login(client)
    response = client.post("/api/v1/complaints", json=report | changes, headers=headers)
    assert response.status_code == 422
    assert connection.scalar(select(Complaint.id)) is None


@pytest.mark.parametrize("role", ["administrator", "department_operator"])
def test_non_citizen_cannot_submit(auth_client, report, role):
    client, connection = auth_client
    headers, _, _ = login(client)
    connection.execute(update(User).values(role_name=role))
    assert client.post("/api/v1/complaints", json=report, headers=headers).status_code == 403
    assert connection.scalar(select(Complaint.id)) is None


def test_anonymous_and_logged_out_requests_are_rejected(auth_client, report):
    client, connection = auth_client
    assert client.post("/api/v1/complaints", json=report).status_code == 401
    headers, _, tokens = login(client)
    client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert client.post("/api/v1/complaints", json=report, headers=headers).status_code == 401
    assert connection.scalar(select(Complaint.id)) is None


def test_submission_keys_are_scoped_to_each_citizen(auth_client, report):
    client, connection = auth_client
    first, _, _ = login(client)
    second, _, _ = login(client, "another@example.com")
    one = client.post("/api/v1/complaints", json=report, headers=first)
    two = client.post("/api/v1/complaints", json=report, headers=second)
    assert one.status_code == two.status_code == 201
    assert one.json()["id"] != two.json()["id"]
    assert connection.scalar(select(func.count()).select_from(Complaint)) == 2


def test_list_is_owned_paginated_and_deterministic(auth_client, report):
    client, _ = auth_client
    owner, _, _ = login(client)
    receipts = [
        client.post(
            "/api/v1/complaints",
            json=report | {"submission_id": str(uuid4()), "title": f"Citizen report {number}"},
            headers=owner,
        ).json()
        for number in range(2)
    ]
    other, other_user, _ = login(client, "another@example.com")
    client.post("/api/v1/complaints", json=report, headers=other)
    response = client.get(f"/api/v1/complaints?limit=1&user_id={other_user['id']}", headers=owner)
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2 and page["limit"] == 1 and page["offset"] == 0
    assert len(page["items"]) == 1
    assert set(page["items"][0]) == {"id", "title", "category", "status", "created_at"}
    expected = sorted([item["id"] for item in receipts], reverse=True)
    assert page["items"][0]["id"] == expected[0]
    second = client.get("/api/v1/complaints?limit=1&offset=1", headers=owner).json()
    assert second["items"][0]["id"] == expected[1]
    assert response.headers["cache-control"] == "no-store"


def test_tracking_cannot_read_another_citizens_complaint(auth_client, report):
    client, _ = auth_client
    owner, _, _ = login(client)
    receipt = client.post("/api/v1/complaints", json=report, headers=owner).json()
    path = f"/api/v1/complaints/{receipt['id']}"
    response = client.get(path, headers=owner)
    assert response.status_code == 200 and response.json() == receipt
    assert response.headers["cache-control"] == "no-store"
    other, _, _ = login(client, "another@example.com")
    forbidden = client.get(path, headers=other)
    missing = client.get(f"/api/v1/complaints/{uuid4()}", headers=other)
    assert forbidden.status_code == missing.status_code == 404
    assert forbidden.json() == missing.json() == {"detail": "Complaint not found"}


def test_empty_list_and_read_authentication(auth_client, report):
    client, _ = auth_client
    assert client.get("/api/v1/complaints").status_code == 401
    owner, _, tokens = login(client)
    assert client.get("/api/v1/complaints", headers=owner).json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }
    receipt = client.post("/api/v1/complaints", json=report, headers=owner).json()
    path = f"/api/v1/complaints/{receipt['id']}"
    assert client.get(path).status_code == 401
    client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert client.get("/api/v1/complaints", headers=owner).status_code == 401
    assert client.get(path, headers=owner).status_code == 401


@pytest.mark.parametrize("role", ["administrator", "department_operator"])
def test_citizen_reads_do_not_grant_administrative_access(auth_client, report, role):
    client, connection = auth_client
    owner, _, _ = login(client)
    receipt = client.post("/api/v1/complaints", json=report, headers=owner).json()
    connection.execute(update(User).values(role_name=role))
    assert client.get("/api/v1/complaints", headers=owner).status_code == 403
    assert client.get(f"/api/v1/complaints/{receipt['id']}", headers=owner).status_code == 403


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=51", "offset=-1", "offset=100001", "limit=invalid"]
)
def test_pagination_bounds(auth_client, query):
    client, _ = auth_client
    owner, _, _ = login(client)
    assert client.get(f"/api/v1/complaints?{query}", headers=owner).status_code == 422
