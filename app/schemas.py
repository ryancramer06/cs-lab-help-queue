"""Validation for data entering the application."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import IssueCategory


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
