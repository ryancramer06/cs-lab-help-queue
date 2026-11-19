from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy.orm import Session

from app.models import IssueCategory, RequestStatus
from app.requests import create_request, get_request
from app.schemas import HelpRequestCreate


@pytest.fixture
def request_session(isolated_postgres_connection):
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.attributes["connection"] = isolated_postgres_connection
    command.upgrade(config, "head")

    # Committing a session releases its savepoint; the outer test transaction still rolls back.
    with Session(
        bind=isolated_postgres_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as session:
        yield session


@pytest.fixture
def submission():
    return HelpRequestCreate(
        student_name=" Taylor Example ",
        assignment="Lab 3",
        issue_category=IssueCategory.DEBUGGING,
        description="My loop never terminates.",
    )


def test_create_and_retrieve_a_committed_request(request_session, submission):
    request = create_request(request_session, submission)
    request_id = request.id
    request_session.commit()
    # Clear the identity map so the lookup has to read the row from PostgreSQL.
    request_session.expunge_all()

    stored = get_request(request_session, request_id)

    assert stored is not None
    assert stored.student_name == "Taylor Example"
    assert stored.assignment == submission.assignment
    assert stored.issue_category == submission.issue_category
    assert stored.description == submission.description
    assert stored.status == RequestStatus.PENDING
    assert stored.created_at.utcoffset() is not None


def test_get_request_returns_none_for_a_missing_id(request_session):
    assert get_request(request_session, 999999) is None


def test_creating_a_request_does_not_commit_the_callers_transaction(
    request_session, submission
):
    request = create_request(request_session, submission)
    request_id = request.id

    request_session.rollback()

    assert get_request(request_session, request_id) is None
