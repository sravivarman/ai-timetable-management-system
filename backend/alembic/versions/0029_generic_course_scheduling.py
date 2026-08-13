"""Separate course activity, grouping, session pattern, and venue.

Revision ID: 0029
Revises: 0028
"""

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_timetable_entry_type", "timetable_entries", type_="check")
    op.create_check_constraint("ck_timetable_entry_type", "timetable_entries", "entry_type IN ('THEORY','LABORATORY','PRACTICAL','CDC','LSM','MINI_PROJECT','PROJECT')")
    op.add_column("courses", sa.Column("grouping_mode", sa.String(20), nullable=True))
    op.add_column("courses", sa.Column("venue_requirement", sa.String(40), nullable=True))
    op.add_column("courses", sa.Column("session_duration", sa.Integer(), nullable=True))
    op.add_column("courses", sa.Column("sessions_per_week", sa.Integer(), nullable=True))
    op.add_column("courses", sa.Column("default_group_count", sa.Integer(), nullable=True))
    op.execute("UPDATE courses SET grouping_mode = CASE WHEN COALESCE(default_lab_group_count, 1) > 1 THEN 'GROUPED' ELSE 'FULL_SECTION' END")
    op.execute("UPDATE courses SET venue_requirement = CASE WHEN course_type = 'LABORATORY' THEN 'LABORATORY_ONLY' WHEN course_type IN ('THEORY', 'CDC') THEN 'CLASSROOM_ONLY' ELSE 'NO_FIXED_VENUE' END")
    op.execute("UPDATE courses SET session_duration = COALESCE(lab_session_duration, 1)")
    op.execute("UPDATE courses SET sessions_per_week = COALESCE(lab_sessions_per_week, weekly_periods)")
    op.execute("UPDATE courses SET default_group_count = COALESCE(default_lab_group_count, 1)")
    for name, type_ in (("grouping_mode", sa.String(20)), ("venue_requirement", sa.String(40)), ("session_duration", sa.Integer()), ("sessions_per_week", sa.Integer()), ("default_group_count", sa.Integer())):
        op.alter_column("courses", name, existing_type=type_, nullable=False)
    op.alter_column("courses", "grouping_mode", server_default=sa.text("'FULL_SECTION'"))
    op.alter_column("courses", "venue_requirement", server_default=sa.text("'CLASSROOM_ONLY'"))
    op.alter_column("courses", "session_duration", server_default=sa.text("1"))
    op.alter_column("courses", "sessions_per_week", server_default=sa.text("1"))
    op.alter_column("courses", "default_group_count", server_default=sa.text("1"))
    op.create_check_constraint("ck_courses_session_duration_positive", "courses", "session_duration >= 1")
    op.create_check_constraint("ck_courses_sessions_per_week_positive", "courses", "sessions_per_week >= 1")
    op.create_check_constraint("ck_courses_default_group_count_positive", "courses", "default_group_count >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_timetable_entry_type", "timetable_entries", type_="check")
    op.create_check_constraint("ck_timetable_entry_type", "timetable_entries", "entry_type IN ('THEORY','LABORATORY','CDC','LSM','MINI_PROJECT','PROJECT')")
    op.drop_constraint("ck_courses_default_group_count_positive", "courses", type_="check")
    op.drop_constraint("ck_courses_sessions_per_week_positive", "courses", type_="check")
    op.drop_constraint("ck_courses_session_duration_positive", "courses", type_="check")
    for name in ("default_group_count", "sessions_per_week", "session_duration", "venue_requirement", "grouping_mode"):
        op.drop_column("courses", name)
