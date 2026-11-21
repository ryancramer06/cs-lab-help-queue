import json
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
import pytest

from app.database import get_session
from app.main import create_app


def test_submit_and_retrieve_request(api_client, request_payload):
    response = api_client.post("/api/requests", json=request_payload)

    assert response.status_code == 201
    request = response.json()
    assert request["student_name"] == request_payload["student_name"]
    assert request["status"] == "pending"
    assert request["created_at"] is not None
    assert request["assigned_ta"] is None
    assert api_client.get(response.headers["location"]).json() == request


@pytest.mark.parametrize("description", [" \t ", "bad\x00text", "bad\ud800text"])
def test_invalid_submission_returns_safe_validation_errors(
    api_client, request_payload, description
):
    request_payload["description"] = description
    # Escaped JSON also covers Unicode that an HTTP client cannot encode directly.
    response = api_client.post(
        "/api/requests", content=json.dumps(request_payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "description"]
    assert "input" not in response.json()["detail"][0]


def test_submission_rejects_server_controlled_fields(api_client, request_payload):
    request_payload["status"] = "resolved"
    assert api_client.post("/api/requests", json=request_payload).status_code == 422


def test_missing_request_returns_not_found(api_client):
    response = api_client.get("/api/requests/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Help request not found"}


def test_request_id_must_be_positive(api_client):
    assert api_client.get("/api/requests/0").status_code == 422


def test_failed_commit_does_not_return_success_or_expose_driver_details(settings, request_payload):
    application = create_app(settings)
    session = Mock(spec=Session)
    session.commit.side_effect = OperationalError("private SQL", {}, Exception("private-password"))
    application.dependency_overrides[get_session] = lambda: session

    with TestClient(application) as client:
        response = client.post("/api/requests", json=request_payload)

    assert response.status_code == 503
    assert "private" not in response.text
