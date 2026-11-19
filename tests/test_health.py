from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.orm import Session
import pytest

from app.database import get_session
from app.main import create_app


def test_liveness_does_not_require_a_database_connection(settings):
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SELECT 1", {}, Exception("private-password-and-host")),
        TimeoutError("private-password-and-host"),
    ],
)
def test_readiness_reports_database_failure_without_internal_details(settings, error):
    application = create_app(settings)
    session = Mock(spec=Session)
    session.execute.side_effect = error
    application.dependency_overrides[get_session] = lambda: session

    with TestClient(application) as client:
        response = client.get("/health/ready")
        liveness = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "private-password-and-host" not in response.text
    assert liveness.status_code == 200


def test_readiness_with_a_real_postgres_connection(postgres_settings):
    application = create_app(postgres_settings)
    with TestClient(application) as client:
        for _ in range(2):
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "database": "connected"}
