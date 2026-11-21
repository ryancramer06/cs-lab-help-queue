"""Validation for data entering the application."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.models import IssueCategory, RequestStatus


class HelpRequestCreate(BaseModel):
    # Keep status, TA assignment, and timestamps out of student submissions.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    student_name: str = Field(min_length=1, max_length=100)
    assignment: str = Field(min_length=1, max_length=120)
    issue_category: IssueCategory
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("student_name", "assignment", "description")
    @classmethod
    def validate_database_text(cls, value: str) -> str:
        # Catch unsupported text here so it becomes a validation error, not a failed INSERT.
        if "\x00" in value:
            raise ValueError("Text cannot contain NUL characters")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Text must contain valid Unicode characters") from None
        return value


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
