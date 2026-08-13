"""Create working days and period timings.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa
revision="0008";down_revision="0007";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("working_days",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("day_name",sa.String(10),nullable=False,unique=True),sa.Column("sequence_number",sa.Integer(),nullable=False,unique=True),sa.Column("is_working_day",sa.Boolean(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")))
 op.create_table("period_timings",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("schedule_type",sa.String(20),nullable=False),sa.Column("period_number",sa.Integer(),nullable=True),sa.Column("start_time",sa.Time(),nullable=False),sa.Column("end_time",sa.Time(),nullable=False),sa.Column("duration_minutes",sa.Integer(),nullable=False),sa.Column("is_instructional",sa.Boolean(),nullable=False),sa.Column("break_type",sa.String(20)),sa.Column("sequence_number",sa.Integer(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()")),sa.UniqueConstraint("schedule_type","period_number",name="uq_period_timing_type_number"))
def downgrade():op.drop_table("period_timings");op.drop_table("working_days")
