"""Support nullable period numbers for non-instructional breaks.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve all instructional period numbers; break slots are sequenced but unnumbered.
    op.execute(sa.text("UPDATE period_timings SET period_number = NULL WHERE is_instructional = false"))
    op.drop_constraint("uq_period_timing_type_number", "period_timings", type_="unique")
    op.alter_column("period_timings", "period_number", existing_type=sa.Integer(), nullable=True)
    op.create_unique_constraint("uq_period_timing_type_sequence", "period_timings", ["schedule_type", "sequence_number"])
    op.create_index(
        "uq_period_timing_instructional_number",
        "period_timings",
        ["schedule_type", "period_number"],
        unique=True,
        postgresql_where=sa.text("period_number IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_period_timing_instructional_or_break",
        "period_timings",
        "(is_instructional AND period_number BETWEEN 1 AND 7) "
        "OR (NOT is_instructional AND period_number IS NULL AND break_type IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_period_timing_instructional_or_break", "period_timings", type_="check")
    op.drop_index("uq_period_timing_instructional_number", table_name="period_timings")
    op.drop_constraint("uq_period_timing_type_sequence", "period_timings", type_="unique")
    # The old schema cannot represent unnumbered breaks. Preserve their rows
    # by assigning non-conflicting legacy numbers before restoring NOT NULL.
    op.execute(sa.text("UPDATE period_timings SET period_number = sequence_number + 7 WHERE period_number IS NULL"))
    op.alter_column("period_timings", "period_number", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("uq_period_timing_type_number", "period_timings", ["schedule_type", "period_number"])
