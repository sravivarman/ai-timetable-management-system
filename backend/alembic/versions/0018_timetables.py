"""Create timetable versions and solver snapshots.
Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa
revision="0018";down_revision="0017";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("timetables",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("academic_term_id",sa.Uuid(),nullable=False),sa.Column("scope_type",sa.String(20)),sa.Column("department_id",sa.Uuid()),sa.Column("program_id",sa.Uuid()),sa.Column("section_id",sa.Uuid()),sa.Column("name",sa.String(255)),sa.Column("status",sa.String(20)),sa.Column("active_version_id",sa.Uuid()),sa.Column("created_by",sa.Uuid()),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
 op.create_table("timetable_versions",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("timetable_id",sa.Uuid()),sa.Column("version_number",sa.Integer()),sa.Column("version_name",sa.String(255)),sa.Column("source_type",sa.String(20)),sa.Column("validation_run_id",sa.Uuid()),sa.Column("solver_status",sa.String(20)),sa.Column("is_active",sa.Boolean()),sa.Column("is_locked",sa.Boolean()),sa.Column("created_by",sa.Uuid()),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("timetable_id","version_number"))
 op.create_table("solver_input_snapshots",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("timetable_version_id",sa.Uuid(),unique=True),sa.Column("snapshot_json",sa.JSON()),sa.Column("input_hash",sa.String(64)),sa.Column("created_at",sa.DateTime(timezone=True)))
def downgrade():op.drop_table("solver_input_snapshots");op.drop_table("timetable_versions");op.drop_table("timetables")
