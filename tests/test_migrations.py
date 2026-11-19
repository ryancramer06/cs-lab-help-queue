from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_offline_migration_preview_does_not_require_database_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid-url-that-must-not-be-used")
    output = StringIO()
    config = Config(PROJECT_ROOT / "alembic.ini", output_buffer=output)

    command.upgrade(config, "head", sql=True)

    assert "BEGIN;" in output.getvalue()
    assert "COMMIT;" in output.getvalue()
    assert "invalid-url-that-must-not-be-used" not in output.getvalue()


@pytest.fixture
def migration_config(isolated_postgres_connection):
    config = Config(PROJECT_ROOT / "alembic.ini")
    config.attributes["connection"] = isolated_postgres_connection
    return config


def test_initial_migration_matches_models_and_sets_database_defaults(
    migration_config, isolated_postgres_connection
):
    command.upgrade(migration_config, "head")
    command.check(migration_config)

    row = isolated_postgres_connection.execute(
        text(
            "INSERT INTO help_requests "
            "(student_name, assignment, issue_category, description) "
            "VALUES (:student, :assignment, :category, :description) "
            "RETURNING id, status, created_at"
        ),
        {
            "student": "Taylor Example",
            "assignment": "Lab 3",
            "category": "debugging",
            "description": "My loop never terminates.",
        },
    ).one()

    assert row.id is not None
    assert row.status == "pending"
    assert row.created_at.utcoffset() is not None


def test_initial_migration_can_be_rolled_back_and_reapplied(
    migration_config, isolated_postgres_connection
):
    command.upgrade(migration_config, "head")
    assert inspect(isolated_postgres_connection).has_table("help_requests")

    command.downgrade(migration_config, "base")
    assert not inspect(isolated_postgres_connection).has_table("help_requests")

    command.upgrade(migration_config, "head")
    assert inspect(isolated_postgres_connection).has_table("help_requests")
    command.check(migration_config)
