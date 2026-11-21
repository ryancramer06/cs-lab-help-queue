"""Database operations for help requests."""

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import HelpRequest, IssueCategory, RequestStatus
from app.schemas import HelpRequestCreate


def create_request(session: Session, submission: HelpRequestCreate) -> HelpRequest:
    request = HelpRequest(**submission.model_dump())
    session.add(request)
    # Fetch the generated ID and defaults now, but let the caller decide when to commit.
    session.flush()
    session.refresh(request)
    return request


def get_request(session: Session, request_id: int) -> HelpRequest | None:
    return session.get(HelpRequest, request_id)


def list_requests(
    session: Session, *, limit: int = 100, offset: int = 0,
    assignment: str | None = None, issue_category: IssueCategory | None = None,
    status: RequestStatus | None = None, active_only: bool = False,
) -> list[HelpRequest]:
    """Return a bounded page of requests, ordered oldest first."""
    # bool is an int subclass, and SQLAlchemy would silently truncate a float here.
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")

    # Requests can share a timestamp, so the ID keeps the ordering consistent between pages.
    statement = (
        _filtered_requests(assignment, issue_category, status, active_only)
        .order_by(HelpRequest.created_at, HelpRequest.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement))


def _filtered_requests(
    assignment: str | None, issue_category: IssueCategory | None,
    status: RequestStatus | None, active_only: bool,
) -> Select[tuple[HelpRequest]]:
    statement = select(HelpRequest)
    if assignment is not None:
        statement = statement.where(HelpRequest.assignment == assignment)
    if issue_category is not None:
        statement = statement.where(HelpRequest.issue_category == issue_category)
    if status is not None:
        statement = statement.where(HelpRequest.status == status)
    if active_only:
        statement = statement.where(HelpRequest.status != RequestStatus.RESOLVED)
    return statement


def count_requests(
    session: Session, *, assignment: str | None = None,
    issue_category: IssueCategory | None = None,
    status: RequestStatus | None = None, active_only: bool = False,
) -> int:
    # Share the predicates so the page total always uses the same filters as its rows.
    statement = _filtered_requests(assignment, issue_category, status, active_only)
    return session.scalar(select(func.count()).select_from(statement.subquery())) or 0


def get_queue_position(session: Session, request: HelpRequest) -> int | None:
    if request.status != RequestStatus.PENDING:
        return None
    earlier = or_(
        HelpRequest.created_at < request.created_at,
        and_(HelpRequest.created_at == request.created_at, HelpRequest.id < request.id),
    )
    waiting_ahead = session.scalar(
        select(func.count()).select_from(HelpRequest).where(
            HelpRequest.status == RequestStatus.PENDING, earlier
        )
    )
    return (waiting_ahead or 0) + 1


def claim_request(session: Session, request_id: int, ta_name: str) -> HelpRequest | None:
    # Check and assign in one UPDATE. Two TAs must never both pass a separate read check.
    statement = (
        update(HelpRequest)
        .where(
            HelpRequest.id == request_id,
            HelpRequest.status == RequestStatus.PENDING,
            HelpRequest.assigned_ta.is_(None),
        )
        .values(assigned_ta=ta_name, claimed_at=func.clock_timestamp())
        .returning(HelpRequest)
        .execution_options(populate_existing=True)
    )
    return session.scalar(statement)
