"""Load and validate application configuration without displaying credentials."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
    )

    database_url: SecretStr
    database_connect_timeout: int = Field(default=5, ge=1, le=30)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        message = (
            "DATABASE_URL must be a postgresql+psycopg URL with a username, "
            "host, and database name"
        )
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and url.username
                and url.host
                and url.database
                and (url.port is None or 1 <= url.port <= 65535)
            )
        except (ArgumentError, ValueError):
            raise ValueError(message) from None
        if not valid:
            raise ValueError(message)
        return value
