"""Backfill and protect timetable timestamps.

Revision ID: 0020
Revises: 0019
"""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def _repair_timestamps(table_name: str) -> None:
    op.execute(sa.text(f"UPDATE {table_name} SET created_at = now() WHERE created_at IS NULL"))
    op.execute(
        sa.text(
            f"UPDATE {table_name} "
            "SET updated_at = COALESCE(created_at, now()) "
            "WHERE updated_at IS NULL"
        )
    )
    op.alter_column(
        table_name,
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        table_name,
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    _repair_timestamps("timetables")
    _repair_timestamps("timetable_versions")


def downgrade() -> None:
    for table_name in ("timetable_versions", "timetables"):
        op.alter_column(
            table_name,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            table_name,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
