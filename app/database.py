"""Database connection pooling and one SQLAlchemy session per request."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import Settings


class Base(DeclarativeBase):
    """Shared metadata for application models and Alembic migrations."""


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        # A connection left in the pool may have gone stale after a database restart.
        pool_pre_ping=True,
        pool_timeout=settings.database_connect_timeout,
        connect_args={"connect_timeout": settings.database_connect_timeout},
        hide_parameters=True,
    )


def get_session(request: Request) -> Iterator[Session]:
    # The context manager closes the session and rolls back unfinished work.
    with request.app.state.session_factory() as session:
        yield session
