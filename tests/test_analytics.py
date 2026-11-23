from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import create_app
from app.models import HelpRequest


def add_record(connection, **changes):
    record = {
        "student_name": "Taylor Example", "assignment": "Lab 4", "issue_category": "debugging",
        "description": "Fictional test request.", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    connection.execute(insert(HelpRequest).values(**(record | changes)))


def test_empty_analytics_has_no_misleading_averages(api_client):
    response = api_client.get("/api/analytics")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["total_requests"] == data["pending_requests"] == data["resolved_requests"] == 0
    assert data["in_progress_requests"] == data["wait_sample_size"] == data["resolution_sample_size"] == 0
    assert data["average_wait_seconds"] is data["average_resolution_seconds"] is None
    assert data["by_category"] == data["by_assignment"] == []
    assert len(data["activity"]) == 14
    assert all(day["count"] == 0 for day in data["activity"])


def test_averages_use_started_and_resolved_requests(api_client, migrated_postgres_connection):
    connection = migrated_postgres_connection
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for wait, duration in [(10, 30), (20, 10)]:
        add_record(connection, status="resolved", assigned_ta="Alex Example",
                   started_at=created + timedelta(minutes=wait),
                   resolved_at=created + timedelta(minutes=wait + duration))
    add_record(connection, status="in_progress", started_at=created + timedelta(minutes=5))
    add_record(connection, assigned_ta="Alex Example", claimed_at=created + timedelta(minutes=1))
    add_record(connection, assignment="Lab 5", issue_category="syntax")

    data = api_client.get("/api/analytics").json()
    assert data["total_requests"] == 5
    assert (data["pending_requests"], data["in_progress_requests"], data["resolved_requests"]) == (2, 1, 2)
    assert data["wait_sample_size"] == 3
    assert data["average_wait_seconds"] == pytest.approx(700)
    assert data["resolution_sample_size"] == 2
    assert data["average_resolution_seconds"] == pytest.approx(1200)
    assert data["by_category"] == [
        {"issue_category": "debugging", "count": 4}, {"issue_category": "syntax", "count": 1},
    ]
    assert data["by_assignment"] == [{"assignment": "Lab 4", "count": 4}, {"assignment": "Lab 5", "count": 1}]
    assert "student_name" not in data and "description" not in data


def test_invalid_or_missing_times_do_not_distort_averages(api_client, migrated_postgres_connection):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_record(migrated_postgres_connection, status="resolved")
    add_record(migrated_postgres_connection, status="resolved", started_at=created - timedelta(minutes=5),
               resolved_at=created)
    add_record(migrated_postgres_connection, status="resolved", started_at=created + timedelta(minutes=10),
               resolved_at=created + timedelta(minutes=5))
    data = api_client.get("/api/analytics").json()
    assert data["resolved_requests"] == 3
    assert data["average_wait_seconds"] == 600
    assert data["wait_sample_size"] == 1
    assert data["average_resolution_seconds"] is None
    assert data["resolution_sample_size"] == 0


def test_activity_uses_utc_days_and_fills_gaps(api_client, migrated_postgres_connection):
    migrated_postgres_connection.execute(text("SET LOCAL TIME ZONE 'Pacific/Honolulu'"))
    initial = api_client.get("/api/analytics").json()
    today = datetime.fromisoformat(initial["generated_at"]).astimezone(timezone.utc).date()
    yesterday = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    # This UTC day differs from the date in the database session's time zone.
    add_record(migrated_postgres_connection, created_at=yesterday + timedelta(hours=1))
    add_record(migrated_postgres_connection, created_at=yesterday - timedelta(days=20))
    data = api_client.get("/api/analytics").json()
    days = {day["date"]: day["count"] for day in data["activity"]}
    assert data["total_requests"] == 2
    assert len(days) == 14
    assert days[yesterday.date().isoformat()] == 1
    assert sum(days.values()) == 1
    dates = [datetime.fromisoformat(day["date"]).date() for day in data["activity"]]
    assert all(later - earlier == timedelta(days=1) for earlier, later in zip(dates, dates[1:]))


def test_assignment_breakdown_is_bounded_and_orders_ties(api_client, migrated_postgres_connection):
    for number in reversed(range(12)):
        add_record(migrated_postgres_connection, assignment=f"Lab {number:02}")
    data = api_client.get("/api/analytics").json()
    assert data["total_assignments"] == 12
    assert len(data["by_assignment"]) == 10
    assert [item["assignment"] for item in data["by_assignment"]] == [f"Lab {number:02}" for number in range(10)]


def test_analytics_reflects_a_completed_workflow(api_client, request_payload):
    record = api_client.post("/api/requests", json=request_payload).json()
    path = f'/api/requests/{record["id"]}'
    actor = {"ta_name": "Alex Example"}
    for action in ("claim", "start", "resolve"):
        assert api_client.post(f"{path}/{action}", json=actor).status_code == 200
    data = api_client.get("/api/analytics").json()
    assert data["resolved_requests"] == data["wait_sample_size"] == data["resolution_sample_size"] == 1
    assert data["pending_requests"] == data["in_progress_requests"] == 0
    assert data["average_wait_seconds"] >= 0
    assert data["average_resolution_seconds"] >= 0
    assert sum(day["count"] for day in data["activity"]) == 1


def test_analytics_database_errors_do_not_expose_details(settings):
    application = create_app(settings)
    session = Mock(spec=Session)
    session.execute.side_effect = OperationalError("private SQL", {}, Exception("private-password"))
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as client:
        response = client.get("/api/analytics")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Database unavailable. Please try again shortly."}
