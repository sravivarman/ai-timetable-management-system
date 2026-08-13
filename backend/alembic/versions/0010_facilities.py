"""Create classroom and laboratory masters.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa
revision="0010";down_revision="0009";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("classrooms",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("room_number",sa.String(50),nullable=False,unique=True),sa.Column("room_name",sa.String(255)),sa.Column("building_name",sa.String(255)),sa.Column("floor_number",sa.Integer()),sa.Column("owning_department_id",sa.Uuid()),sa.Column("is_primary_classroom",sa.Boolean(),nullable=False),sa.Column("is_shareable",sa.Boolean(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.ForeignKeyConstraint(["owning_department_id"],["departments.id"],ondelete="SET NULL"))
 op.create_table("laboratories",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("laboratory_code",sa.String(50),nullable=False,unique=True),sa.Column("laboratory_name",sa.String(255),nullable=False),sa.Column("room_number",sa.String(50),nullable=False,unique=True),sa.Column("owning_department_id",sa.Uuid(),nullable=False),sa.Column("is_shareable_across_departments",sa.Boolean(),nullable=False),sa.Column("is_available_all_periods",sa.Boolean(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.ForeignKeyConstraint(["owning_department_id"],["departments.id"],ondelete="RESTRICT"))
def downgrade():op.drop_table("laboratories");op.drop_table("classrooms")
