"""HTTP endpoints for student requests and TA actions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import HelpRequest
from app.requests import (
    claim_request, create_request, get_queue_position, get_request, get_request_page,
    resolve_request, start_request,
)
from app.schemas import (
    ApiError, HelpRequestCreate, HelpRequestPage, HelpRequestRead, QueuePosition, RequestListQuery, TaAction,
)


NOT_FOUND_RESPONSE = {404: {"model": ApiError, "description": "Help request not found"}}
ACTION_ERROR_RESPONSES = {
    **NOT_FOUND_RESPONSE,
    409: {"model": ApiError, "description": "Request state or assigned TA conflicts with this action"},
}
router = APIRouter(
    prefix="/api/requests", tags=["Requests"],
    responses={503: {"model": ApiError, "description": "Database unavailable"}},
)
DatabaseSession = Annotated[Session, Depends(get_session)]
# The primary key is a PostgreSQL INTEGER, so reject larger IDs before querying it.
RequestId = Annotated[int, Path(ge=1, le=2**31 - 1)]


@router.get("", response_model=HelpRequestPage)
def read_queue(
    query: Annotated[RequestListQuery, Query()], session: DatabaseSession
) -> HelpRequestPage:
    """List active requests by default; use status=resolved to view history."""
    filters = query.model_dump(exclude={"limit", "offset"})
    filters["active_only"] = query.status is None
    requests, total = get_request_page(session, limit=query.limit, offset=query.offset, **filters)
    return HelpRequestPage(
        items=[HelpRequestRead.model_validate(request) for request in requests],
        total=total, limit=query.limit, offset=query.offset,
    )


@router.post("", response_model=HelpRequestRead, status_code=201)
def submit_request(
    submission: HelpRequestCreate, session: DatabaseSession, response: Response
) -> HelpRequest:
    request = create_request(session, submission)
    # Commit before returning success so a failed write never looks like a saved request.
    session.commit()
    response.headers["Location"] = f"/api/requests/{request.id}"
    return request


@router.get("/{request_id}", response_model=HelpRequestRead, responses=NOT_FOUND_RESPONSE)
def read_request(request_id: RequestId, session: DatabaseSession) -> HelpRequest:
    request = get_request(session, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Help request not found")
    return request


@router.get("/{request_id}/position", response_model=QueuePosition, responses=NOT_FOUND_RESPONSE)
def read_queue_position(request_id: RequestId, session: DatabaseSession) -> QueuePosition:
    position = get_queue_position(session, request_id)
    if position is None:
        raise HTTPException(status_code=404, detail="Help request not found")
    return position


def _save_action(
    session: Session, request_id: int, updated: HelpRequest | None
) -> HelpRequest:
    if updated is None:
        if get_request(session, request_id) is None:
            raise HTTPException(status_code=404, detail="Help request not found")
        raise HTTPException(
            status_code=409,
            detail="The request's state or assigned TA does not allow this action.",
        )
    session.commit()
    return updated


@router.post("/{request_id}/claim", response_model=HelpRequestRead, responses=ACTION_ERROR_RESPONSES)
def claim(request_id: RequestId, action: TaAction, session: DatabaseSession) -> HelpRequest:
    return _save_action(session, request_id, claim_request(session, request_id, action.ta_name))


@router.post("/{request_id}/start", response_model=HelpRequestRead, responses=ACTION_ERROR_RESPONSES)
def start(request_id: RequestId, action: TaAction, session: DatabaseSession) -> HelpRequest:
    return _save_action(session, request_id, start_request(session, request_id, action.ta_name))


@router.post("/{request_id}/resolve", response_model=HelpRequestRead, responses=ACTION_ERROR_RESPONSES)
def resolve(request_id: RequestId, action: TaAction, session: DatabaseSession) -> HelpRequest:
    return _save_action(session, request_id, resolve_request(session, request_id, action.ta_name))
