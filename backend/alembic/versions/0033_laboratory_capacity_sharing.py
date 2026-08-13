"""Add generic laboratory capacity sharing.

Revision ID: 0033
Revises: 0032
"""

from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("laboratories", sa.Column("capacity", sa.Integer(), nullable=True))
    op.add_column(
        "laboratories",
        sa.Column("concurrent_usage_mode", sa.String(length=24), nullable=False, server_default="EXCLUSIVE"),
    )
    op.create_check_constraint("ck_laboratory_capacity_positive", "laboratories", "capacity IS NULL OR capacity > 0")
    op.create_check_constraint(
        "ck_laboratory_concurrent_usage_mode",
        "laboratories",
        "concurrent_usage_mode IN ('EXCLUSIVE','CAPACITY_SHARED')",
    )
    op.create_check_constraint(
        "ck_laboratory_shared_capacity_required",
        "laboratories",
        "concurrent_usage_mode = 'EXCLUSIVE' OR capacity IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_laboratory_shared_capacity_required", "laboratories", type_="check")
    op.drop_constraint("ck_laboratory_concurrent_usage_mode", "laboratories", type_="check")
    op.drop_constraint("ck_laboratory_capacity_positive", "laboratories", type_="check")
    op.drop_column("laboratories", "concurrent_usage_mode")
    op.drop_column("laboratories", "capacity")
