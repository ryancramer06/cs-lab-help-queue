"""Validation for data entering the application."""

from pydantic import BaseModel, ConfigDict, Field

from app.models import IssueCategory


class HelpRequestCreate(BaseModel):
    # Keep status, TA assignment, and timestamps out of student submissions.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    student_name: str = Field(min_length=1, max_length=100)
    assignment: str = Field(min_length=1, max_length=120)
    issue_category: IssueCategory
    description: str = Field(min_length=1, max_length=1000)
