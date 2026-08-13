"""Add combined teaching groups and logical common-class events.

Revision ID: 0030
Revises: 0029
"""

from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("classrooms", sa.Column("capacity", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_classrooms_capacity_positive", "classrooms", "capacity IS NULL OR capacity > 0")
    op.create_table(
        "combined_teaching_groups",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("academic_term_id", sa.Uuid(), nullable=False),
        sa.Column("group_code", sa.String(80), nullable=False), sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False), sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("preferred_classroom_id", sa.Uuid(), nullable=True), sa.Column("preferred_laboratory_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["preferred_classroom_id"], ["classrooms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["preferred_laboratory_id"], ["laboratories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("academic_term_id", "group_code", name="uq_combined_teaching_term_code"),
    )
    for column in ("academic_term_id", "group_code", "course_id", "faculty_id", "is_active"):
        op.create_index(f"ix_combined_teaching_groups_{column}", "combined_teaching_groups", [column])
    op.create_table(
        "combined_teaching_group_members",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("combined_teaching_group_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["combined_teaching_group_id"], ["combined_teaching_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("combined_teaching_group_id", "course_offering_id", name="uq_combined_teaching_group_offering"),
    )
    op.create_index("ix_combined_teaching_group_members_group", "combined_teaching_group_members", ["combined_teaching_group_id"])
    op.create_index("ix_combined_teaching_group_members_offering", "combined_teaching_group_members", ["course_offering_id"])
    op.create_table(
        "combined_teaching_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("timetable_version_id", sa.Uuid(), nullable=False),
        sa.Column("combined_teaching_group_id", sa.Uuid(), nullable=False), sa.Column("working_day_id", sa.Uuid(), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False), sa.Column("session_length", sa.Integer(), nullable=False),
        sa.Column("faculty_id", sa.Uuid(), nullable=False), sa.Column("classroom_id", sa.Uuid(), nullable=True),
        sa.Column("laboratory_id", sa.Uuid(), nullable=True), sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["timetable_version_id"], ["timetable_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["combined_teaching_group_id"], ["combined_teaching_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["working_day_id"], ["working_days.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["laboratory_id"], ["laboratories.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    for column in ("timetable_version_id", "combined_teaching_group_id", "working_day_id", "faculty_id", "classroom_id", "laboratory_id"):
        op.create_index(f"ix_combined_teaching_events_{column}", "combined_teaching_events", [column])
    op.add_column("timetable_entries", sa.Column("combined_teaching_event_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_timetable_entries_combined_event", "timetable_entries", "combined_teaching_events", ["combined_teaching_event_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_timetable_entries_combined_teaching_event_id", "timetable_entries", ["combined_teaching_event_id"])


def downgrade() -> None:
    op.drop_index("ix_timetable_entries_combined_teaching_event_id", table_name="timetable_entries")
    op.drop_constraint("fk_timetable_entries_combined_event", "timetable_entries", type_="foreignkey")
    op.drop_column("timetable_entries", "combined_teaching_event_id")
    op.drop_table("combined_teaching_events")
    op.drop_table("combined_teaching_group_members")
    op.drop_table("combined_teaching_groups")
    op.drop_constraint("ck_classrooms_capacity_positive", "classrooms", type_="check")
    op.drop_column("classrooms", "capacity")
