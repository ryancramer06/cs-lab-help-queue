"""FastAPI entry point and application health checks."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import create_database_engine, get_session


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = create_database_engine(settings)
        application.state.session_factory = sessionmaker(
            bind=engine, expire_on_commit=False
        )
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="CS Lab Help Queue",
        description="A programming lab help queue for students and teaching assistants.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/health/ready",
        tags=["Health"],
        responses={503: {"description": "PostgreSQL is unavailable"}},
    )
    def readiness(session: Annotated[Session, Depends(get_session)]) -> JSONResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            # Driver errors can contain credentials and internal connection details.
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "database": "unavailable"},
            )
        return JSONResponse(content={"status": "ok", "database": "connected"})

    return application
