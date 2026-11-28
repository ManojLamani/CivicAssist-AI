from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi import HTTPException
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.complaint_status import change_status, record_status
from app.models import Complaint, ComplaintStatus, ComplaintStatusHistory, User


def account(client, connection, email, role="citizen"):
    payload = {"email": email, "password": "long-test-password"}
    user = client.post("/api/v1/auth/register", json=payload | {"full_name": "Test User"}).json()
    connection.execute(update(User).where(User.id == UUID(user["id"])).values(role_name=role))
    tokens = client.post("/api/v1/auth/login", json=payload).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}, UUID(user["id"])


@pytest.fixture
def status_case(auth_client):
    client, connection = auth_client
    citizen, citizen_id = account(client, connection, "citizen@example.com")
    receipt = client.post(
        "/api/v1/complaints",
        headers=citizen,
        json={
            "submission_id": str(uuid4()),
            "title": "Damaged road surface",
            "description": "A broken road surface needs inspection.",
            "category": "roads",
            "location": "Test street near the park",
        },
    ).json()
    admin, admin_id = account(client, connection, "admin@example.com", "administrator")
    return client, connection, receipt, citizen, admin, admin_id


def test_admin_flow_records_actor_and_citizen_visible_history(status_case):
    client, connection, receipt, citizen, admin, admin_id = status_case
    path = f"/api/v1/admin/complaints/{receipt['id']}"
    page = client.get("/api/v1/admin/complaints", headers=admin)
    assert page.status_code == 200 and page.json()["total"] == 1
    assert page.headers["cache-control"] == "no-store"
    assert client.get(path, headers=admin).json()["allowed_statuses"] == ["acknowledged"]
    status = "submitted"
    for target in ["acknowledged", "in_progress", "resolved", "in_progress", "resolved", "closed"]:
        response = client.patch(
            path + "/status",
            headers=admin,
            json={"expected_status": status, "status": target, "note": f"Reviewed: {target}."},
        )
        assert response.status_code == 200
        assert response.json()["status"] == target
        assert response.headers["cache-control"] == "no-store"
        status = target
    assert response.json()["allowed_statuses"] == []
    events = connection.execute(
        select(ComplaintStatusHistory.__table__).order_by(ComplaintStatusHistory.id)
    ).all()
    assert len(events) == 7 and all(event.actor_id == admin_id for event in events[1:])
    assert events[-1].from_status == "resolved" and events[-1].to_status == "closed"
    tracked = client.get(f"/api/v1/complaints/{receipt['id']}", headers=citizen).json()
    assert tracked["status"] == "closed" and len(tracked["history"]) == 7
    assert tracked["history"][-1]["note"] == "Reviewed: closed."
    assert "actor_id" not in tracked["history"][-1]


@pytest.mark.parametrize("role", ["citizen", "department_operator"])
def test_admin_routes_reject_other_roles(status_case, role):
    client, connection, receipt, citizen, admin, admin_id = status_case
    connection.execute(update(User).where(User.id == admin_id).values(role_name=role))
    path = f"/api/v1/admin/complaints/{receipt['id']}"
    assert client.get("/api/v1/admin/complaints", headers=admin).status_code == 403
    assert client.get(path, headers=admin).status_code == 403
    assert (
        client.patch(
            path + "/status",
            headers=admin,
            json={"expected_status": "submitted", "status": "acknowledged", "note": "Reviewed."},
        ).status_code
        == 403
    )
    assert connection.scalar(select(Complaint.status)) == "submitted"
    assert connection.scalar(select(func.count()).select_from(ComplaintStatusHistory)) == 1


def test_anonymous_admin_requests_are_rejected(auth_client):
    client, _ = auth_client
    path = f"/api/v1/admin/complaints/{uuid4()}"
    assert client.get("/api/v1/admin/complaints").status_code == 401
    assert client.get(path).status_code == 401
    assert (
        client.patch(
            path + "/status",
            json={"expected_status": "submitted", "status": "acknowledged", "note": "Reviewed."},
        ).status_code
        == 401
    )


def test_stale_and_skipped_transitions_are_rejected_without_history(status_case):
    client, connection, receipt, _, admin, _ = status_case
    path = f"/api/v1/admin/complaints/{receipt['id']}/status"
    for body in [
        {"expected_status": "submitted", "status": "resolved", "note": "Invalid skip."},
        {"expected_status": "acknowledged", "status": "in_progress", "note": "Stale view."},
        {"expected_status": "submitted", "status": "submitted", "note": "No change."},
    ]:
        assert client.patch(path, headers=admin, json=body).status_code == 409
    assert connection.scalar(select(Complaint.status)) == "submitted"
    assert connection.scalar(select(func.count()).select_from(ComplaintStatusHistory)) == 1


@pytest.mark.parametrize(
    "changes",
    [{"note": " "}, {"note": "x" * 1001}, {"status": "assigned"}, {"actor_id": str(uuid4())}],
)
def test_invalid_status_updates_are_rejected(status_case, changes):
    client, connection, receipt, _, admin, _ = status_case
    response = client.patch(
        f"/api/v1/admin/complaints/{receipt['id']}/status",
        headers=admin,
        json={"expected_status": "submitted", "status": "acknowledged", "note": "Reviewed."}
        | changes,
    )
    assert response.status_code == 422
    assert connection.scalar(select(Complaint.status)) == "submitted"


def test_history_cannot_be_edited_or_individually_deleted(status_case):
    _, connection, _, _, _, _ = status_case
    for statement in [
        update(ComplaintStatusHistory).values(note="Rewritten"),
        delete(ComplaintStatusHistory),
    ]:
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(statement)
    assert connection.scalar(select(func.count()).select_from(ComplaintStatusHistory)) == 1
    # Explicit complaint deletion is the only permitted cascade cleanup path.
    connection.execute(delete(Complaint))
    assert connection.scalar(select(ComplaintStatusHistory.id)) is None


def test_migration_backfills_original_submission_and_refuses_lossy_downgrade(migrated_database):
    connection, config = migrated_database
    command.downgrade(config, "0003_complaints")
    user_id, complaint_id = uuid4(), uuid4()
    connection.execute(
        User.__table__.insert().values(
            id=user_id, email="old@example.com", full_name="Test", password_hash="unused"
        )
    )
    connection.execute(
        Complaint.__table__.insert().values(
            id=complaint_id,
            user_id=user_id,
            submission_id=uuid4(),
            title="Existing complaint",
            description="Existing saved description.",
            category="roads",
            location="Existing test street",
        )
    )
    command.upgrade(config, "head")
    event = connection.execute(select(ComplaintStatusHistory.__table__)).mappings().one()
    assert (
        event["from_status"] is None
        and event["to_status"] == "submitted"
        and event["actor_id"] == user_id
    )
    assert event["created_at"] == connection.scalar(select(Complaint.created_at))
    command.check(config)
    connection.execute(update(Complaint).values(status="acknowledged"))
    with pytest.raises(DBAPIError), connection.begin_nested():
        command.downgrade(config, "0003_complaints")
    assert "complaint_status_history" in inspect(connection).get_table_names(
        schema=connection.dialect.default_schema_name
    )
    assert connection.scalar(select(Complaint.status)) == "acknowledged"


def test_concurrent_updates_create_only_one_status_event(committed_database):
    with Session(committed_database) as session:
        actor = User(
            email="admin-race@example.com",
            full_name="Admin",
            password_hash="unused",
            role_name="administrator",
        )
        session.add(actor)
        session.flush()
        complaint = Complaint(
            user_id=actor.id,
            submission_id=uuid4(),
            title="Concurrent report",
            description="Concurrent status update test.",
            category="roads",
            location="Test street",
        )
        session.add(complaint)
        session.flush()
        record_status(session, complaint, actor.id, None, "Complaint submitted.")
        session.commit()
        complaint_id, actor_id = complaint.id, actor.id
    barrier = Barrier(2)

    def change(_):
        with Session(committed_database) as session:
            barrier.wait(timeout=10)
            try:
                change_status(
                    session,
                    complaint_id,
                    actor_id,
                    ComplaintStatus.SUBMITTED,
                    ComplaintStatus.ACKNOWLEDGED,
                    "Acknowledged by an administrator.",
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(change, range(2))) == [200, 409]
    with Session(committed_database) as session:
        assert session.scalar(select(func.count()).select_from(ComplaintStatusHistory)) == 2
