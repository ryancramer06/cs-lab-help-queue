"""Create help requests table

Revision ID: dbc5dfbd078c
Revises:
Create Date: 2026-11-18 21:10:09.254962

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dbc5dfbd078c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "help_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_name", sa.String(length=100), nullable=False),
        sa.Column("assignment", sa.String(length=120), nullable=False),
        sa.Column(
            "issue_category",
            sa.Enum(
                "syntax", "debugging", "conceptual", "environment", "other",
                name="issue_category", native_enum=False, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "in_progress", "resolved",
                name="request_status", native_enum=False, create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("assigned_ta", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("help_requests")
