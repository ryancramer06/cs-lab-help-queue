"""Read-only analytics endpoint for the dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import get_analytics
from app.database import get_session
from app.schemas import AnalyticsRead, ApiError


router = APIRouter(
    prefix="/api/analytics", tags=["Analytics"],
    responses={503: {"model": ApiError, "description": "Database unavailable"}},
)


@router.get("", response_model=AnalyticsRead)
def read_analytics(session: Annotated[Session, Depends(get_session)]) -> AnalyticsRead:
    """Overall totals, top ten assignments, and fourteen days of activity in UTC.

    Wait time ends when work starts; resolution time measures time spent helping.
    Averages exclude incomplete or invalid timestamp pairs and are null without samples.
    """
    return get_analytics(session)
