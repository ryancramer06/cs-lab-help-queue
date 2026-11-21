import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import create_database_engine, get_session
from app.main import create_app


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch):
    # Tests supply configuration explicitly; integration tests use TEST_DATABASE_URL.
    for variable in ("DATABASE_URL", "DATABASE_CONNECT_TIMEOUT"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test_user:test_password@127.0.0.1:1/test_queue",
        database_connect_timeout=1,
    )


@pytest.fixture
def postgres_settings() -> Settings:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL connection test")
    return Settings(_env_file=None, database_url=database_url)


@pytest.fixture
def isolated_postgres_connection(postgres_settings):
    engine = create_database_engine(postgres_settings)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema_name = f"test_{uuid4().hex}"
                connection.execute(CreateSchema(schema_name))
                connection.execute(
                    text("SELECT set_config('search_path', :schema, true)"),
                    {"schema": schema_name},
                )
                yield connection
            finally:
                # PostgreSQL rolls back the temporary schema, tables, and test rows.
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def migrated_postgres_connection(isolated_postgres_connection):
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.attributes["connection"] = isolated_postgres_connection
    command.upgrade(config, "head")
    return isolated_postgres_connection


@pytest.fixture
def api_client(settings, migrated_postgres_connection):
    application = create_app(settings)

    def test_session():
        with Session(
            bind=migrated_postgres_connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    application.dependency_overrides[get_session] = test_session
    with TestClient(application) as client:
        yield client


@pytest.fixture
def request_payload():
    return {
        "student_name": "Taylor Example",
        "assignment": "Lab 3",
        "issue_category": "debugging",
        "description": "My loop never terminates.",
    }
