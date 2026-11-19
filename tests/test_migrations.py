from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_offline_migration_preview_does_not_require_database_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid-url-that-must-not-be-used")
    output = StringIO()
    config = Config(PROJECT_ROOT / "alembic.ini", output_buffer=output)

    command.upgrade(config, "head", sql=True)

    assert "BEGIN;" in output.getvalue()
    assert "COMMIT;" in output.getvalue()
    assert "invalid-url-that-must-not-be-used" not in output.getvalue()
