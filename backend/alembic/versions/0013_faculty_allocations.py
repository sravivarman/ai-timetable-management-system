"""Create faculty allocation entities.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

def _timestamps():
    return [sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("theory_faculty_allocations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("course_offering_id", sa.Uuid(), nullable=False), sa.Column("faculty_id", sa.Uuid(), nullable=False), *_timestamps(), sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"], ondelete="RESTRICT"), sa.UniqueConstraint("course_offering_id", "faculty_id", name="uq_theory_allocation_offering_faculty"))
    op.create_table("laboratory_faculty_allocations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("course_offering_id", sa.Uuid(), nullable=False), sa.Column("faculty_id", sa.Uuid(), nullable=False), sa.Column("role_type", sa.String(20), nullable=False), sa.Column("required_with_main_faculty_id", sa.Uuid()), sa.Column("alternative_group_code", sa.String(100)), sa.Column("minimum_sessions_per_week", sa.Integer()), sa.Column("maximum_sessions_per_week", sa.Integer()), *_timestamps(), sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["required_with_main_faculty_id"], ["faculty.id"], ondelete="RESTRICT"), sa.UniqueConstraint("course_offering_id", "faculty_id", "role_type", name="uq_laboratory_allocation_offering_faculty_role"), sa.CheckConstraint("role_type IN ('MAIN', 'SUPPORTING')", name="ck_lab_allocation_role_type"), sa.CheckConstraint("minimum_sessions_per_week IS NULL OR minimum_sessions_per_week >= 1", name="ck_lab_min_sessions"), sa.CheckConstraint("maximum_sessions_per_week IS NULL OR maximum_sessions_per_week >= minimum_sessions_per_week", name="ck_lab_max_sessions"))
    op.create_table("laboratory_session_faculty_rules", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("laboratory_faculty_allocation_id", sa.Uuid(), nullable=False), sa.Column("session_number", sa.Integer(), nullable=False), sa.Column("is_mandatory_for_session", sa.Boolean(), nullable=False), *_timestamps(), sa.ForeignKeyConstraint(["laboratory_faculty_allocation_id"], ["laboratory_faculty_allocations.id"], ondelete="RESTRICT"), sa.UniqueConstraint("laboratory_faculty_allocation_id", "session_number", name="uq_lab_session_faculty_rule"), sa.CheckConstraint("session_number >= 1", name="ck_lab_rule_session_number"))
    for name, table, column in (("ix_theory_faculty_allocations_course_offering_id", "theory_faculty_allocations", "course_offering_id"), ("ix_theory_faculty_allocations_faculty_id", "theory_faculty_allocations", "faculty_id"), ("ix_laboratory_faculty_allocations_course_offering_id", "laboratory_faculty_allocations", "course_offering_id"), ("ix_laboratory_faculty_allocations_faculty_id", "laboratory_faculty_allocations", "faculty_id"), ("ix_laboratory_faculty_allocations_role_type", "laboratory_faculty_allocations", "role_type"), ("ix_lab_session_rule_allocation_id", "laboratory_session_faculty_rules", "laboratory_faculty_allocation_id")):
        op.create_index(name, table, [column])

def downgrade() -> None:
    op.drop_table("laboratory_session_faculty_rules")
    op.drop_table("laboratory_faculty_allocations")
    op.drop_table("theory_faculty_allocations")
