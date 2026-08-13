"""Add timetable entry audit and status transition history.

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0023";down_revision="0022";branch_labels=None;depends_on=None

def upgrade():
 op.create_table("timetable_entry_audits",
  sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column("timetable_entry_id",postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column("timetable_version_id",postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column("action_type",sa.String(20),nullable=False),
  sa.Column("old_values_json",sa.JSON(),nullable=True),sa.Column("new_values_json",sa.JSON(),nullable=True),
  sa.Column("reason",sa.String(1000),nullable=True),sa.Column("performed_by",postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
  sa.ForeignKeyConstraint(["timetable_version_id"],["timetable_versions.id"],ondelete="CASCADE"),
  sa.ForeignKeyConstraint(["performed_by"],["users.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"))
 for column in ("timetable_entry_id","timetable_version_id","action_type","performed_by"):op.create_index(f"ix_timetable_entry_audits_{column}","timetable_entry_audits",[column])
 op.create_table("timetable_status_history",
  sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("timetable_id",postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column("from_status",sa.String(20),nullable=False),sa.Column("to_status",sa.String(20),nullable=False),sa.Column("reason",sa.String(1000),nullable=True),
  sa.Column("performed_by",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
  sa.ForeignKeyConstraint(["timetable_id"],["timetables.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["performed_by"],["users.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"))
 for column in ("timetable_id","performed_by"):op.create_index(f"ix_timetable_status_history_{column}","timetable_status_history",[column])

def downgrade():
 op.drop_table("timetable_status_history");op.drop_table("timetable_entry_audits")
