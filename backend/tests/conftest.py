import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import get_auth_settings


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
