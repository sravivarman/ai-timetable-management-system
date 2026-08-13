"""Allow multiple deterministic snapshots per timetable version.

Revision ID: 0019
Revises: 0018
"""
from alembic import op
revision="0019";down_revision="0018";branch_labels=None;depends_on=None
def upgrade():
 op.drop_constraint("solver_input_snapshots_timetable_version_id_key","solver_input_snapshots",type_="unique")
 op.create_unique_constraint("uq_solver_snapshot_version_hash","solver_input_snapshots",["timetable_version_id","input_hash"])
 op.create_index("ix_solver_input_snapshots_timetable_version_id","solver_input_snapshots",["timetable_version_id"])
 op.create_index("ix_solver_input_snapshots_input_hash","solver_input_snapshots",["input_hash"])
def downgrade():
 op.drop_index("ix_solver_input_snapshots_input_hash",table_name="solver_input_snapshots");op.drop_index("ix_solver_input_snapshots_timetable_version_id",table_name="solver_input_snapshots");op.drop_constraint("uq_solver_snapshot_version_hash","solver_input_snapshots",type_="unique");op.create_unique_constraint("solver_input_snapshots_timetable_version_id_key","solver_input_snapshots",["timetable_version_id"])
