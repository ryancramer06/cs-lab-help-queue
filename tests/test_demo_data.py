from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import get_analytics
from app.models import HelpRequest
from scripts.seed_demo import seed_demo_data


def test_demo_data_has_consistent_workflows_and_refuses_a_second_seed(migrated_postgres_connection):
    now = datetime.now(timezone.utc)
    with Session(bind=migrated_postgres_connection, join_transaction_mode="create_savepoint") as session:
        count = seed_demo_data(session, now=now)
        records = list(session.scalars(select(HelpRequest)))
        assert count == len(records) > 70
        for record in records:
            assert any(marker in record.student_name for marker in ("Example", "Sample", "Demo"))
            times = [record.created_at, record.claimed_at, record.started_at, record.resolved_at]
            present = [timestamp for timestamp in times if timestamp is not None]
            assert present == sorted(present)
            assert all(timestamp <= now for timestamp in present)
        data = get_analytics(session)
        assert data.total_requests == count
        assert data.pending_requests == 4 and data.in_progress_requests == 2
        assert data.resolved_requests == count - 6
        assert data.average_wait_seconds > 0 and data.average_resolution_seconds > 0
        assert len(data.by_category) == 5 and len(data.by_assignment) == 4
        with pytest.raises(ValueError, match="empty help_requests"):
            seed_demo_data(session)
        assert session.scalar(select(func.count()).select_from(HelpRequest)) == count


def test_demo_data_preserves_an_existing_request(api_client, request_payload, migrated_postgres_connection):
    record = api_client.post("/api/requests", json=request_payload).json()
    with Session(bind=migrated_postgres_connection, join_transaction_mode="create_savepoint") as session:
        with pytest.raises(ValueError, match="empty help_requests"):
            seed_demo_data(session)
    assert api_client.get(f'/api/requests/{record["id"]}').json() == record
    assert api_client.get("/api/requests").json()["total"] == 1
