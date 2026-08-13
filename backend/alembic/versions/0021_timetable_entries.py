"""Create timetable entry persistence.

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision="0021";down_revision="0020";branch_labels=None;depends_on=None

def upgrade():
 op.create_table(
  "timetable_entries",
  sa.Column("id",sa.Uuid(),primary_key=True),
  sa.Column("timetable_version_id",sa.Uuid(),sa.ForeignKey("timetable_versions.id",ondelete="CASCADE"),nullable=False),
  sa.Column("course_offering_id",sa.Uuid(),sa.ForeignKey("course_offerings.id",ondelete="RESTRICT"),nullable=False),
  sa.Column("section_id",sa.Uuid(),sa.ForeignKey("sections.id",ondelete="RESTRICT"),nullable=False),
  sa.Column("faculty_id",sa.Uuid(),sa.ForeignKey("faculty.id",ondelete="RESTRICT")),
  sa.Column("laboratory_faculty_allocation_id",sa.Uuid(),sa.ForeignKey("laboratory_faculty_allocations.id",ondelete="RESTRICT")),
  sa.Column("classroom_id",sa.Uuid(),sa.ForeignKey("classrooms.id",ondelete="RESTRICT")),
  sa.Column("laboratory_id",sa.Uuid(),sa.ForeignKey("laboratories.id",ondelete="RESTRICT")),
  sa.Column("student_batch_id",sa.Uuid(),sa.ForeignKey("student_batches.id",ondelete="RESTRICT")),
  sa.Column("working_day_id",sa.Uuid(),sa.ForeignKey("working_days.id",ondelete="RESTRICT"),nullable=False),
  sa.Column("period_number",sa.Integer(),nullable=False),sa.Column("session_length",sa.Integer(),nullable=False,server_default="1"),
  sa.Column("entry_type",sa.String(20),nullable=False),sa.Column("is_manual",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("is_locked",sa.Boolean(),nullable=False,server_default=sa.false()),
  sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
  sa.CheckConstraint("period_number BETWEEN 1 AND 7",name="ck_timetable_entry_period"),sa.CheckConstraint("session_length IN (1,2,3)",name="ck_timetable_entry_session_length"),sa.CheckConstraint("period_number + session_length - 1 <= 7",name="ck_timetable_entry_session_end"),sa.CheckConstraint("entry_type IN ('THEORY','LABORATORY','CDC','LSM','MINI_PROJECT','PROJECT')",name="ck_timetable_entry_type"),
 )
 for column in ("timetable_version_id","course_offering_id","section_id","faculty_id","classroom_id","laboratory_id","student_batch_id","working_day_id","period_number","entry_type","is_manual","is_locked"):
  op.create_index(f"ix_timetable_entries_{column}","timetable_entries",[column])

def downgrade():op.drop_table("timetable_entries")
