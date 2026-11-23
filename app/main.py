"""FastAPI entry point and application health checks."""

from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.api import router as request_router
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
    application.include_router(request_router)
    static_directory = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_directory), name="static")

    @application.get("/", response_class=FileResponse, include_in_schema=False)
    def student_page() -> FileResponse:
        return FileResponse(static_directory / "index.html", headers={"Cache-Control": "no-cache"})

    @application.get("/ta", response_class=FileResponse, include_in_schema=False)
    def ta_page() -> FileResponse:
        return FileResponse(static_directory / "ta.html", headers={"Cache-Control": "no-cache"})

    @application.middleware("http")
    async def live_request_data(request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            # Queue state changes often, and responses contain student request details.
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/static/"):
            # Keep cached scripts and styles in sync with the HTML after an update.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_, error: RequestValidationError) -> Response:
        # Report the bad fields without echoing student text or exception objects.
        details = [
            {key: item[key] for key in ("loc", "msg", "type")}
            for item in error.errors()
        ]
        return Response(
            content=json.dumps({"detail": details}, ensure_ascii=True),
            status_code=422,
            media_type="application/json",
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_failure(_, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable. Please try again shortly."},
        )

    @application.get("/health", tags=["Health"])
    def health(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-store"
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
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            content={"status": "ok", "database": "connected"},
            headers={"Cache-Control": "no-store"},
        )

    return application
