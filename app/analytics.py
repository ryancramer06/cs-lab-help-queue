"""Queue statistics computed in PostgreSQL without loading student records."""

from datetime import timedelta, timezone

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session

from app.models import HelpRequest, RequestStatus
from app.schemas import AnalyticsRead


ACTIVITY_DAYS = 14
ASSIGNMENT_LIMIT = 10


def _group_counts(grouped, key: str):
    """Keep grouped results inside the same SQL statement as the summary."""
    return select(func.jsonb_agg(aggregate_order_by(
        func.jsonb_build_object(key, grouped.c.group_key, "count", grouped.c.count),
        grouped.c.count.desc(), grouped.c.group_key.asc(),
    ))).scalar_subquery()


def get_analytics(session: Session) -> AnalyticsRead:
    request = HelpRequest
    valid_wait = and_(
        request.status.in_([RequestStatus.IN_PROGRESS, RequestStatus.RESOLVED]),
        request.started_at.is_not(None), request.started_at >= request.created_at,
    )
    valid_resolution = and_(
        valid_wait, request.status == RequestStatus.RESOLVED,
        request.resolved_at.is_not(None), request.resolved_at >= request.started_at,
    )
    categories = select(
        request.issue_category.label("group_key"), func.count().label("count"),
    ).group_by(request.issue_category).subquery()
    assignments = select(
        request.assignment.label("group_key"), func.count().label("count"),
    ).group_by(request.assignment).order_by(
        func.count().desc(), request.assignment,
    ).limit(ASSIGNMENT_LIMIT).subquery()

    # Explicit UTC dates keep the chart stable across server and browser time zones.
    created_day = cast(func.timezone("UTC", request.created_at), Date)
    today = cast(func.timezone("UTC", func.statement_timestamp()), Date)
    activity = select(
        created_day.label("group_key"), func.count().label("count"),
    ).where(
        created_day >= today - (ACTIVITY_DAYS - 1), created_day <= today,
    ).group_by(created_day).subquery()

    statement = select(
        func.statement_timestamp().label("generated_at"),
        func.count().label("total_requests"),
        func.count().filter(request.status == RequestStatus.PENDING).label("pending_requests"),
        func.count().filter(request.status == RequestStatus.IN_PROGRESS).label("in_progress_requests"),
        func.count().filter(request.status == RequestStatus.RESOLVED).label("resolved_requests"),
        func.avg(func.extract("epoch", request.started_at - request.created_at))
        .filter(valid_wait).label("average_wait_seconds"),
        func.count().filter(valid_wait).label("wait_sample_size"),
        func.avg(func.extract("epoch", request.resolved_at - request.started_at))
        .filter(valid_resolution).label("average_resolution_seconds"),
        func.count().filter(valid_resolution).label("resolution_sample_size"),
        func.count(func.distinct(request.assignment)).label("total_assignments"),
        _group_counts(categories, "issue_category").label("by_category"),
        _group_counts(assignments, "assignment").label("by_assignment"),
        _group_counts(activity, "date").label("activity"),
    ).select_from(request)

    # A single statement prevents totals and charts from describing different queue snapshots.
    result = dict(session.execute(statement).mappings().one())
    result["by_category"] = result["by_category"] or []
    result["by_assignment"] = result["by_assignment"] or []
    counts = {day["date"]: day["count"] for day in result["activity"] or []}
    end = result["generated_at"].astimezone(timezone.utc).date()
    result["activity"] = [
        {"date": day, "count": counts.get(day.isoformat(), 0)}
        for day in (end - timedelta(days=offset) for offset in reversed(range(ACTIVITY_DAYS)))
    ]
    return AnalyticsRead(**result)
