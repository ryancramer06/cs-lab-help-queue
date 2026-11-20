from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy.orm import Session

from app.models import IssueCategory, RequestStatus
from app.requests import create_request, get_request, list_requests
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


def test_request_creation_preserves_unicode_text(request_session, submission):
    data = submission.model_dump()
    data.update(student_name="Zoë Example", description="print('café')\n\t# Check λ here")
    request = create_request(request_session, HelpRequestCreate.model_validate(data))
    request_id = request.id
    request_session.commit()
    request_session.expunge_all()

    stored = get_request(request_session, request_id)

    assert stored.student_name == data["student_name"]
    assert stored.description == data["description"]


def test_creating_a_request_does_not_commit_the_callers_transaction(
    request_session, submission
):
    request = create_request(request_session, submission)
    request_id = request.id

    request_session.rollback()

    assert get_request(request_session, request_id) is None


def test_list_requests_returns_an_empty_page_when_no_requests_exist(request_session):
    assert list_requests(request_session) == []


def test_list_requests_orders_by_creation_time_then_id(request_session, submission):
    newest = create_request(request_session, submission)
    first_waiting = create_request(request_session, submission)
    second_waiting = create_request(request_session, submission)
    earlier = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    newest.created_at = earlier + timedelta(minutes=1)
    first_waiting.created_at = earlier
    second_waiting.created_at = earlier
    request_session.flush()

    requests = list_requests(request_session)

    assert [request.id for request in requests] == [
        first_waiting.id, second_waiting.id, newest.id
    ]


def test_list_requests_respects_page_size_and_offset(request_session, submission):
    requests = [create_request(request_session, submission) for _ in range(3)]

    page = list_requests(request_session, limit=1, offset=1)

    assert [request.id for request in page] == [requests[1].id]
    assert len(list_requests(request_session, limit=100)) == 3
    assert list_requests(request_session, offset=3) == []


@pytest.mark.parametrize("pagination", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_requests_rejects_invalid_pagination(request_session, pagination):
    with pytest.raises(ValueError):
        list_requests(request_session, **pagination)
