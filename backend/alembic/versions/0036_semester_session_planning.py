"""Add semester session planning and date-specific resource exceptions.

Revision ID: 0036
Revises: 0035
"""

from alembic import op
import sqlalchemy as sa


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_offering_semester_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("academic_term_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("total_sessions_required", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total_sessions_required >= 0", name="ck_semester_requirement_non_negative"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_offering_id", name="uq_semester_requirement_offering"),
    )
    op.create_index("ix_course_offering_semester_requirements_course_offering_id", "course_offering_semester_requirements", ["course_offering_id"])
    op.create_index("ix_semester_requirements_term_active", "course_offering_semester_requirements", ["academic_term_id", "is_active"])
    op.create_table(
        "resource_date_exceptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("academic_term_id", sa.Uuid(), nullable=False),
        sa.Column("exception_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Integer(), nullable=True),
        sa.Column("period_end", sa.Integer(), nullable=True),
        sa.Column("availability_status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("availability_status IN ('AVAILABLE', 'UNAVAILABLE')", name="ck_resource_date_exception_status"),
        sa.CheckConstraint("(period_start IS NULL AND period_end IS NULL) OR (period_start BETWEEN 1 AND 7 AND period_end BETWEEN period_start AND 7)", name="ck_resource_date_exception_period_range"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resource_date_exceptions_resource_type", "resource_date_exceptions", ["resource_type"])
    op.create_index("ix_resource_date_exceptions_resource_id", "resource_date_exceptions", ["resource_id"])
    op.create_index("ix_resource_date_exceptions_academic_term_id", "resource_date_exceptions", ["academic_term_id"])
    op.create_index("ix_resource_date_exceptions_exception_date", "resource_date_exceptions", ["exception_date"])
    op.create_index("ix_resource_date_exceptions_lookup", "resource_date_exceptions", ["resource_type", "resource_id", "academic_term_id", "exception_date", "is_active"])
    op.create_table(
        "timetable_session_progress_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timetable_id", sa.Uuid(), nullable=False),
        sa.Column("timetable_version_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_sessions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["timetable_id"], ["timetables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["timetable_version_id"], ["timetable_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("timetable_version_id", "workflow_status", "course_offering_id", name="uq_session_progress_snapshot"),
    )
    for column in ("timetable_id", "timetable_version_id", "course_offering_id", "workflow_status"):
        op.create_index(f"ix_timetable_session_progress_snapshots_{column}", "timetable_session_progress_snapshots", [column])


def downgrade() -> None:
    for column in ("workflow_status", "course_offering_id", "timetable_version_id", "timetable_id"):
        op.drop_index(f"ix_timetable_session_progress_snapshots_{column}", table_name="timetable_session_progress_snapshots")
    op.drop_table("timetable_session_progress_snapshots")
    op.drop_index("ix_resource_date_exceptions_lookup", table_name="resource_date_exceptions")
    op.drop_index("ix_resource_date_exceptions_exception_date", table_name="resource_date_exceptions")
    op.drop_index("ix_resource_date_exceptions_academic_term_id", table_name="resource_date_exceptions")
    op.drop_index("ix_resource_date_exceptions_resource_id", table_name="resource_date_exceptions")
    op.drop_index("ix_resource_date_exceptions_resource_type", table_name="resource_date_exceptions")
    op.drop_table("resource_date_exceptions")
    op.drop_index("ix_semester_requirements_term_active", table_name="course_offering_semester_requirements")
    op.drop_index("ix_course_offering_semester_requirements_course_offering_id", table_name="course_offering_semester_requirements")
    op.drop_table("course_offering_semester_requirements")
