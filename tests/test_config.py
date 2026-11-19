import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_is_required():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "database_url" in str(error.value)


def test_connection_timeout_defaults_to_five_seconds(settings):
    configuration = Settings(_env_file=None, database_url=settings.database_url)

    assert configuration.database_connect_timeout == 5


@pytest.mark.parametrize(
    "database_url",
    [
        "",
        "not-a-url-containing-secret",
        "sqlite:///test.db",
        "postgresql://user:secret@localhost/test",
        "postgresql+psycopg://user:secret@localhost",
        "postgresql+psycopg://user:secret@localhost:invalid/test",
        "postgresql+psycopg://user:secret@localhost:70000/test",
    ],
)
def test_invalid_database_configuration_is_rejected_without_showing_secrets(database_url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=database_url)

    assert "DATABASE_URL must be" in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("timeout", [0, 31])
def test_connection_timeout_is_bounded(settings, timeout):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url=settings.database_url,
            database_connect_timeout=timeout,
        )


def test_environment_variables_override_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://file_user:file_secret@localhost/file_db\n"
        "DATABASE_CONNECT_TIMEOUT=8\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://env_user:env_secret@localhost/env_db"
    )
    monkeypatch.delenv("DATABASE_CONNECT_TIMEOUT", raising=False)

    settings = Settings(_env_file=env_file)

    assert "env_user" in settings.database_url.get_secret_value()
    assert "env_secret" not in repr(settings)
    assert settings.database_connect_timeout == 8
