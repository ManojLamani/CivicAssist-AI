import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_auth_settings
from app.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def test_signing_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-signing-secret-never-use-outside-tests")
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


@pytest.fixture
def migrated_database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            # Only this randomly named schema is touched; all test changes are rolled back.
            schema = f"test_{uuid4().hex}"
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            # Shadow any migration version table in public to keep tests independent.
            connection.execute(
                text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)")
            )
            connection.dialect.default_schema_name = schema
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            yield connection, config
            transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def auth_client(migrated_database):
    connection, _ = migrated_database

    def session_override():
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            yield client, connection
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def committed_database():
    """Independent connections for concurrency tests, confined to a disposable schema."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = f"test_{uuid4().hex}"
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            connection.execute(
                text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)")
            )
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine.execution_options(schema_translate_map={None: schema})
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
