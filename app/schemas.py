"""Validation for data entering the application."""

from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field

from app.models import IssueCategory, RequestStatus


def validate_database_text(value: str) -> str:
    # Catch unsupported text here so it becomes a validation error, not a failed INSERT.
    if "\x00" in value:
        raise ValueError("Text cannot contain NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must contain valid Unicode characters") from None
    return value


DatabaseText = Annotated[str, AfterValidator(validate_database_text)]


class HelpRequestCreate(BaseModel):
    # Keep status, TA assignment, and timestamps out of student submissions.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    student_name: DatabaseText = Field(min_length=1, max_length=100)
    assignment: DatabaseText = Field(min_length=1, max_length=120)
    issue_category: IssueCategory
    description: DatabaseText = Field(min_length=1, max_length=1000)


class HelpRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_name: str
    assignment: str
    issue_category: IssueCategory
    description: str
    status: RequestStatus
    assigned_ta: str | None
    created_at: AwareDatetime
    claimed_at: AwareDatetime | None
    started_at: AwareDatetime | None
    resolved_at: AwareDatetime | None


class RequestListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    assignment: DatabaseText | None = Field(default=None, min_length=1, max_length=120)
    issue_category: IssueCategory | None = None
    status: RequestStatus | None = None
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=2**63 - 1)


class HelpRequestPage(BaseModel):
    items: list[HelpRequestRead]
    total: int
    limit: int
    offset: int


class QueuePosition(BaseModel):
    request_id: int
    position: int | None
