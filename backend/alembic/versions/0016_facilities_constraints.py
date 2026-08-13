"""Create classroom assignments and laboratory blocks.
Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa
revision="0016";down_revision="0015";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("section_classroom_assignments",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("section_id",sa.Uuid(),nullable=False),sa.Column("classroom_id",sa.Uuid(),nullable=False),sa.Column("academic_term_id",sa.Uuid(),nullable=False),sa.Column("is_primary",sa.Boolean(),nullable=False),sa.Column("effective_from",sa.Date()),sa.Column("effective_to",sa.Date()),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.ForeignKeyConstraint(["section_id"],["sections.id"]),sa.ForeignKeyConstraint(["classroom_id"],["classrooms.id"]),sa.ForeignKeyConstraint(["academic_term_id"],["academic_terms.id"]),sa.UniqueConstraint("section_id","classroom_id","academic_term_id"))
 op.create_table("laboratory_availability_blocks",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("laboratory_id",sa.Uuid(),nullable=False),sa.Column("academic_term_id",sa.Uuid(),nullable=False),sa.Column("working_day_id",sa.Uuid(),nullable=False),sa.Column("period_number",sa.Integer(),nullable=False),sa.Column("reason",sa.String(255)),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.ForeignKeyConstraint(["laboratory_id"],["laboratories.id"]),sa.ForeignKeyConstraint(["academic_term_id"],["academic_terms.id"]),sa.ForeignKeyConstraint(["working_day_id"],["working_days.id"]),sa.UniqueConstraint("laboratory_id","academic_term_id","working_day_id","period_number"),sa.CheckConstraint("period_number BETWEEN 1 AND 7"))
def downgrade():op.drop_table("laboratory_availability_blocks");op.drop_table("section_classroom_assignments")
