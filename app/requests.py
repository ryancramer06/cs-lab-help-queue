"""Database operations for help requests."""

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
