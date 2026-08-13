"""Create persisted CP-SAT solver runs.

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa

revision="0022";down_revision="0021";branch_labels=None;depends_on=None

def upgrade():
 op.create_table("solver_runs",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("timetable_version_id",sa.Uuid(),sa.ForeignKey("timetable_versions.id",ondelete="CASCADE"),nullable=False),sa.Column("solver_input_snapshot_id",sa.Uuid(),sa.ForeignKey("solver_input_snapshots.id",ondelete="RESTRICT"),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("runtime_seconds",sa.Float()),sa.Column("objective_value",sa.Float()),sa.Column("best_bound",sa.Float()),sa.Column("generated_entry_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("message",sa.String(1000)),sa.Column("statistics_json",sa.JSON()),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
 for column in ("timetable_version_id","solver_input_snapshot_id","status"):op.create_index(f"ix_solver_runs_{column}","solver_runs",[column])

def downgrade():op.drop_table("solver_runs")
