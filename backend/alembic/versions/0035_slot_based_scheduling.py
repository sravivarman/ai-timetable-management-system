"""Add generic actual-date scheduling slots alongside weekly scheduling.

Revision ID: 0035
Revises: 0034
"""

from alembic import op
import sqlalchemy as sa


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduling_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("academic_term_id", sa.Uuid(), nullable=False),
        sa.Column("slot_code", sa.String(length=30), nullable=False),
        sa.Column("slot_name", sa.String(length=255), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sequence_number > 0", name="ck_scheduling_slot_positive_sequence"),
        sa.CheckConstraint("end_date >= start_date", name="ck_scheduling_slot_date_range"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("academic_term_id", "slot_code", name="uq_scheduling_slot_term_code"),
        sa.UniqueConstraint("academic_term_id", "sequence_number", name="uq_scheduling_slot_term_sequence"),
    )
    op.create_index("ix_scheduling_slots_term_active", "scheduling_slots", ["academic_term_id", "is_active"])
    op.create_table(
        "scheduling_slot_working_dates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheduling_slot_id", sa.Uuid(), nullable=False),
        sa.Column("working_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scheduling_slot_id"], ["scheduling_slots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheduling_slot_id", "working_date", name="uq_scheduling_slot_working_date"),
    )
    op.create_index("ix_scheduling_slot_working_dates_scheduling_slot_id", "scheduling_slot_working_dates", ["scheduling_slot_id"])
    op.create_index("ix_scheduling_slot_working_dates_active_date", "scheduling_slot_working_dates", ["working_date", "is_active"])
    op.create_table(
        "slot_course_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheduling_slot_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("sessions_required", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sessions_required >= 0", name="ck_slot_requirement_non_negative"),
        sa.ForeignKeyConstraint(["scheduling_slot_id"], ["scheduling_slots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheduling_slot_id", "course_offering_id", name="uq_slot_course_requirement"),
    )
    op.create_index("ix_slot_requirements_slot_active", "slot_course_requirements", ["scheduling_slot_id", "is_active"])
    op.create_index("ix_slot_requirements_offering_active", "slot_course_requirements", ["course_offering_id", "is_active"])
    for table in ("timetables", "timetable_versions", "validation_runs"):
        op.add_column(table, sa.Column("scheduling_mode", sa.String(length=20), server_default="WEEKLY", nullable=False))
        op.add_column(table, sa.Column("scheduling_slot_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_scheduling_slot", table, "scheduling_slots", ["scheduling_slot_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_timetables_scheduling_mode", "timetables", ["scheduling_mode"])
    op.create_index("ix_timetables_scheduling_slot_id", "timetables", ["scheduling_slot_id"])
    op.create_index("ix_timetable_versions_scheduling_mode", "timetable_versions", ["scheduling_mode"])
    op.create_index("ix_timetable_versions_scheduling_slot_id", "timetable_versions", ["scheduling_slot_id"])
    op.create_index("ix_validation_runs_scheduling_mode", "validation_runs", ["scheduling_mode"])
    op.create_index("ix_validation_runs_scheduling_slot_id", "validation_runs", ["scheduling_slot_id"])
    op.create_check_constraint("ck_timetable_scheduling_mode_slot", "timetables", "(scheduling_mode = 'WEEKLY' AND scheduling_slot_id IS NULL) OR (scheduling_mode = 'SLOT_BASED' AND scheduling_slot_id IS NOT NULL)")
    op.create_check_constraint("ck_timetable_version_scheduling_mode_slot", "timetable_versions", "(scheduling_mode = 'WEEKLY' AND scheduling_slot_id IS NULL) OR (scheduling_mode = 'SLOT_BASED' AND scheduling_slot_id IS NOT NULL)")
    op.create_check_constraint("ck_validation_run_scheduling_mode_slot", "validation_runs", "(scheduling_mode = 'WEEKLY' AND scheduling_slot_id IS NULL) OR (scheduling_mode = 'SLOT_BASED' AND scheduling_slot_id IS NOT NULL)")

    op.add_column("timetable_entries", sa.Column("actual_date", sa.Date(), nullable=True))
    op.create_index("ix_timetable_entries_actual_date", "timetable_entries", ["actual_date"])
    op.create_index("ix_timetable_entries_version_date_period", "timetable_entries", ["timetable_version_id", "actual_date", "period_number"])
    op.add_column("combined_teaching_events", sa.Column("actual_date", sa.Date(), nullable=True))
    op.create_index("ix_combined_teaching_events_actual_date", "combined_teaching_events", ["actual_date"])


def downgrade() -> None:
    op.drop_index("ix_combined_teaching_events_actual_date", table_name="combined_teaching_events")
    op.drop_column("combined_teaching_events", "actual_date")
    op.drop_index("ix_timetable_entries_version_date_period", table_name="timetable_entries")
    op.drop_index("ix_timetable_entries_actual_date", table_name="timetable_entries")
    op.drop_column("timetable_entries", "actual_date")
    op.drop_constraint("ck_validation_run_scheduling_mode_slot", "validation_runs", type_="check")
    op.drop_constraint("ck_timetable_version_scheduling_mode_slot", "timetable_versions", type_="check")
    op.drop_constraint("ck_timetable_scheduling_mode_slot", "timetables", type_="check")
    op.drop_index("ix_timetable_versions_scheduling_slot_id", table_name="timetable_versions")
    op.drop_index("ix_timetable_versions_scheduling_mode", table_name="timetable_versions")
    op.drop_index("ix_timetables_scheduling_slot_id", table_name="timetables")
    op.drop_index("ix_timetables_scheduling_mode", table_name="timetables")
    op.drop_index("ix_validation_runs_scheduling_slot_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_scheduling_mode", table_name="validation_runs")
    for table in ("validation_runs", "timetable_versions", "timetables"):
        op.drop_constraint(f"fk_{table}_scheduling_slot", table, type_="foreignkey")
        op.drop_column(table, "scheduling_slot_id")
        op.drop_column(table, "scheduling_mode")
    op.drop_index("ix_slot_requirements_offering_active", table_name="slot_course_requirements")
    op.drop_index("ix_slot_requirements_slot_active", table_name="slot_course_requirements")
    op.drop_table("slot_course_requirements")
    op.drop_index("ix_scheduling_slot_working_dates_active_date", table_name="scheduling_slot_working_dates")
    op.drop_index("ix_scheduling_slot_working_dates_scheduling_slot_id", table_name="scheduling_slot_working_dates")
    op.drop_table("scheduling_slot_working_dates")
    op.drop_index("ix_scheduling_slots_term_active", table_name="scheduling_slots")
    op.drop_table("scheduling_slots")
