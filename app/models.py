"""Persistent help request records."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RequestStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class IssueCategory(StrEnum):
    SYNTAX = "syntax"
    DEBUGGING = "debugging"
    CONCEPTUAL = "conceptual"
    ENVIRONMENT = "environment"
    OTHER = "other"


class HelpRequest(Base):
    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_name: Mapped[str] = mapped_column(String(100))
    assignment: Mapped[str] = mapped_column(String(120))
    issue_category: Mapped[IssueCategory] = mapped_column(
        Enum(
            IssueCategory,
            values_callable=lambda categories: [category.value for category in categories],
            native_enum=False,
            create_constraint=True,
            name="issue_category",
            validate_strings=True,
        )
    )
    description: Mapped[str] = mapped_column(String(1000))
    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            native_enum=False,
            create_constraint=True,
            name="request_status",
            validate_strings=True,
        ),
        server_default="pending",
    )
    assigned_ta: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
