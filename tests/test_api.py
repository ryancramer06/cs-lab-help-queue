import json
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy import func, update
from sqlalchemy.orm import Session
import pytest

from app.database import get_session
from app.main import create_app
from app.models import HelpRequest, RequestStatus


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


@pytest.fixture
def queue_records(api_client, request_payload, migrated_postgres_connection):
    first = api_client.post("/api/requests", json=request_payload).json()
    second = api_client.post(
        "/api/requests", json={**request_payload, "assignment": "Lab 4", "issue_category": "environment"}
    ).json()
    resolved = api_client.post(
        "/api/requests", json={**request_payload, "issue_category": "syntax"}
    ).json()
    migrated_postgres_connection.execute(
        update(HelpRequest).where(HelpRequest.id == resolved["id"]).values(
            status=RequestStatus.RESOLVED, resolved_at=func.now()
        )
    )
    return first, second, resolved


def test_queue_lists_active_requests_with_page_totals(api_client, queue_records):
    response = api_client.get("/api/requests", params={"limit": 1, "offset": 1})
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["limit"] == 1 and page["offset"] == 1
    assert [item["id"] for item in page["items"]] == [queue_records[1]["id"]]


def test_queue_filters_combine_and_trim_assignment(api_client, queue_records):
    response = api_client.get(
        "/api/requests", params={"assignment": " Lab 3 ", "issue_category": "debugging", "status": "pending"}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == queue_records[0]["id"]


def test_resolved_requests_remain_available_in_history(api_client, queue_records):
    response = api_client.get("/api/requests", params={"status": "resolved"})
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == queue_records[2]["id"]


def test_empty_queue_returns_an_empty_page(api_client):
    response = api_client.get("/api/requests")
    assert response.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 2**63},
        {"status": "unknown"}, {"issue_category": "unknown"},
        {"assignment": "   "}, {"unexpected": "value"},
    ],
)
def test_invalid_queue_filters_are_rejected(api_client, query):
    assert api_client.get("/api/requests", params=query).status_code == 422


def test_position_counts_pending_requests_across_pages(api_client, queue_records):
    for position, request in enumerate(queue_records[:2], start=1):
        response = api_client.get(f'/api/requests/{request["id"]}/position')
        assert response.json() == {"request_id": request["id"], "position": position}
    resolved = queue_records[2]
    assert api_client.get(f'/api/requests/{resolved["id"]}/position').json()["position"] is None
