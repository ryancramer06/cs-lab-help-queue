import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import HelpRequest, IssueCategory, RequestStatus


@pytest.fixture
def model_connection(isolated_postgres_connection):
    Base.metadata.create_all(isolated_postgres_connection)
    return isolated_postgres_connection


def test_new_help_request_has_pending_status_and_creation_time(model_connection):
    with Session(bind=model_connection, join_transaction_mode="create_savepoint") as session:
        request = HelpRequest(
            student_name="Taylor Example",
            assignment="Lab 3",
            issue_category=IssueCategory.DEBUGGING,
            description="My loop never terminates.",
        )
        session.add(request)
        session.flush()
        session.refresh(request)

        assert request.id is not None
        assert request.status == RequestStatus.PENDING
        assert request.created_at.utcoffset() is not None
        assert request.assigned_ta is None
        assert request.claimed_at is None
        assert request.started_at is None
        assert request.resolved_at is None


@pytest.mark.parametrize(
    "status,category", [("unknown", "debugging"), ("pending", "unknown")]
)
def test_database_rejects_unknown_status_or_category(model_connection, status, category):
    # Raw SQL verifies PostgreSQL constraints independently of ORM validation.
    with pytest.raises(IntegrityError):
        with model_connection.begin_nested():
            model_connection.execute(
                text(
                    "INSERT INTO help_requests "
                    "(student_name, assignment, description, status, issue_category) "
                    "VALUES (:student_name, :assignment, :description, :status, :category)"
                ),
                {
                    "student_name": "Taylor Example",
                    "assignment": "Lab 3",
                    "description": "My loop never terminates.",
                    "status": status,
                    "category": category,
                },
            )
