"""HTTP endpoints for student requests and TA actions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import HelpRequest
from app.requests import create_request, get_request
from app.schemas import HelpRequestCreate, HelpRequestRead


router = APIRouter(prefix="/api/requests", tags=["Requests"])
DatabaseSession = Annotated[Session, Depends(get_session)]
RequestId = Annotated[int, Path(ge=1)]


@router.post("", response_model=HelpRequestRead, status_code=201)
def submit_request(
    submission: HelpRequestCreate, session: DatabaseSession, response: Response
) -> HelpRequest:
    request = create_request(session, submission)
    # Commit before returning success so a failed write never looks like a saved request.
    session.commit()
    response.headers["Location"] = f"/api/requests/{request.id}"
    return request


@router.get("/{request_id}", response_model=HelpRequestRead)
def read_request(request_id: RequestId, session: DatabaseSession) -> HelpRequest:
    request = get_request(session, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Help request not found")
    return request
