"""Database operations for help requests."""

from sqlalchemy import Select, and_, case, func, or_, select, true, update
from sqlalchemy.orm import Session, aliased

from app.models import HelpRequest, IssueCategory, RequestStatus
from app.schemas import HelpRequestCreate, QueuePosition


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
    _validate_pagination(limit, offset)

    # Requests can share a timestamp, so the ID keeps the ordering consistent between pages.
    statement = (
        _filtered_requests(assignment, issue_category, status, active_only)
        .order_by(HelpRequest.created_at, HelpRequest.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement))


def _validate_pagination(limit: int, offset: int) -> None:
    # bool is an int subclass, and SQLAlchemy would silently truncate a float here.
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")


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


def get_request_page(
    session: Session, *, limit: int = 100, offset: int = 0,
    assignment: str | None = None,
    issue_category: IssueCategory | None = None,
    status: RequestStatus | None = None, active_only: bool = False,
) -> tuple[list[HelpRequest], int]:
    _validate_pagination(limit, offset)
    matching = _filtered_requests(assignment, issue_category, status, active_only).cte("matching_requests")
    page = (
        select(matching).order_by(matching.c.created_at, matching.c.id)
        .limit(limit).offset(offset).subquery("request_page")
    )
    totals = select(func.count().label("total")).select_from(matching).subquery("request_totals")
    request = aliased(HelpRequest, page)
    # One statement gives both reads the same snapshot. Keep the count even if the page is empty.
    statement = (
        select(request, totals.c.total)
        .select_from(totals.outerjoin(page, true()))
        .order_by(request.created_at, request.id)
    )
    rows = session.execute(statement).all()
    return [request for request, _ in rows if request is not None], rows[0][1]


def get_queue_position(session: Session, request_id: int) -> QueuePosition | None:
    request = aliased(HelpRequest)
    earlier = or_(
        HelpRequest.created_at < request.created_at,
        and_(HelpRequest.created_at == request.created_at, HelpRequest.id < request.id),
    )
    waiting_ahead = (
        select(func.count()).select_from(HelpRequest).where(
            HelpRequest.status == RequestStatus.PENDING, earlier
        )
        .correlate(request).scalar_subquery()
    )
    # Read the student's status and the waiting count in one snapshot, just like the queue page.
    statement = select(
        request.id.label("request_id"),
        case((request.status == RequestStatus.PENDING, waiting_ahead + 1)).label("position"),
    ).where(request.id == request_id)
    row = session.execute(statement).one_or_none()
    return QueuePosition(request_id=row.request_id, position=row.position) if row is not None else None


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


def start_request(session: Session, request_id: int, ta_name: str) -> HelpRequest | None:
    statement = (
        update(HelpRequest)
        .where(
            HelpRequest.id == request_id,
            HelpRequest.status == RequestStatus.PENDING,
            HelpRequest.assigned_ta == ta_name,
            HelpRequest.claimed_at.is_not(None),
            HelpRequest.started_at.is_(None),
        )
        .values(status=RequestStatus.IN_PROGRESS, started_at=func.clock_timestamp())
        .returning(HelpRequest)
        .execution_options(populate_existing=True)
    )
    return session.scalar(statement)


def resolve_request(session: Session, request_id: int, ta_name: str) -> HelpRequest | None:
    statement = (
        update(HelpRequest)
        .where(
            HelpRequest.id == request_id,
            HelpRequest.status == RequestStatus.IN_PROGRESS,
            HelpRequest.assigned_ta == ta_name,
            HelpRequest.started_at.is_not(None),
        )
        .values(status=RequestStatus.RESOLVED, resolved_at=func.clock_timestamp())
        .returning(HelpRequest)
        .execution_options(populate_existing=True)
    )
    return session.scalar(statement)
