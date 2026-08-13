"""Backfill and protect timetable validation timestamps.

Revision ID: 0024
Revises: 0023
"""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE validation_runs "
            "SET started_at = COALESCE(created_at, now()) "
            "WHERE started_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE validation_runs "
            "SET created_at = COALESCE(started_at, now()) "
            "WHERE created_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE validation_runs "
            "SET completed_at = COALESCE(started_at, created_at, now()) "
            "WHERE completed_at IS NULL"
        )
    )
    op.execute(sa.text("UPDATE validation_issues SET created_at = now() WHERE created_at IS NULL"))

    for column_name in ("started_at", "completed_at", "created_at"):
        op.alter_column(
            "validation_runs",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
    op.alter_column(
        "validation_issues",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "validation_issues",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    for column_name in ("created_at", "completed_at", "started_at"):
        op.alter_column(
            "validation_runs",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
