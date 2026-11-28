from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Department, DepartmentOperator, Role, User


def test_migration_matches_models_and_can_be_reapplied(migrated_database):
    connection, config = migrated_database
    assert set(connection.scalars(select(Role.name))) == {
        "citizen",
        "administrator",
        "department_operator",
    }
    connection.execute(text("CREATE TABLE external_table (id integer)"))
    command.check(config)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    tables = inspect(connection).get_table_names(schema=connection.dialect.default_schema_name)
    assert "users" not in tables
    assert "external_table" in tables
    assert connection.scalar(text("SELECT PostGIS_Version()"))
    command.upgrade(config, "head")
    assert "users" in inspect(connection).get_table_names(
        schema=connection.dialect.default_schema_name
    )


def test_persistence_defaults_and_rollback(migrated_database):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        user = User(
            email="citizen@example.test", full_name="Test Citizen", password_hash="test-hash"
        )
        session.add(user)
        session.commit()
        assert session.get(User, user.id).role_name == "citizen"
        assert user.created_at.tzinfo is not None
        session.add(Department(name="Test Department", city="Test City"))
        session.flush()
        session.rollback()
        assert session.scalar(select(Department)) is None
        assert session.get(User, user.id) is not None


@pytest.mark.parametrize("email", ["citizen@example.test", "Citizen@example.test", " "])
def test_email_constraints(migrated_database, email):
    connection, _ = migrated_database
    values = {"email": "citizen@example.test", "full_name": "Test", "password_hash": "test-hash"}
    connection.execute(User.__table__.insert().values(**values))
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(User.__table__.insert().values(**(values | {"email": email})))


def test_foreign_keys_and_membership_uniqueness(migrated_database):
    connection, _ = migrated_database
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            DepartmentOperator.__table__.insert().values(user_id=uuid4(), department_id=uuid4())
        )
    user_id, department_id = uuid4(), uuid4()
    connection.execute(
        User.__table__.insert().values(
            id=user_id,
            email="operator@example.test",
            full_name="Operator",
            password_hash="test-hash",
            role_name="department_operator",
        )
    )
    connection.execute(
        Department.__table__.insert().values(
            id=department_id, name="Test Department", city="Test City"
        )
    )
    membership = DepartmentOperator.__table__.insert().values(
        user_id=user_id, department_id=department_id
    )
    connection.execute(membership)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(membership)
