"""Database operations for help requests."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HelpRequest
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
    session: Session, *, limit: int = 100, offset: int = 0
) -> list[HelpRequest]:
    """Return a bounded page of requests, ordered oldest first."""
    # bool is an int subclass, and SQLAlchemy would silently truncate a float here.
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")

    # Requests can share a timestamp, so the ID keeps the ordering consistent between pages.
    statement = (
        select(HelpRequest)
        .order_by(HelpRequest.created_at, HelpRequest.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement))
