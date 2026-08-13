from alembic import op
import sqlalchemy as sa
revision="0017";down_revision="0016";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("validation_runs",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("academic_term_id",sa.Uuid(),nullable=False),sa.Column("scope_type",sa.String(20),nullable=False),sa.Column("department_id",sa.Uuid()),sa.Column("program_id",sa.Uuid()),sa.Column("section_id",sa.Uuid()),sa.Column("status",sa.String(20),nullable=False),sa.Column("total_checks",sa.Integer()),sa.Column("passed_checks",sa.Integer()),sa.Column("failed_checks",sa.Integer()),sa.Column("warning_checks",sa.Integer()),sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("created_by",sa.Uuid(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)))
 op.create_table("validation_issues",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("validation_run_id",sa.Uuid(),nullable=False),sa.Column("severity",sa.String(10)),sa.Column("issue_code",sa.String(100)),sa.Column("entity_type",sa.String(100)),sa.Column("entity_id",sa.Uuid()),sa.Column("message",sa.String(1000)),sa.Column("details",sa.JSON()),sa.Column("created_at",sa.DateTime(timezone=True)))
def downgrade():op.drop_table("validation_issues");op.drop_table("validation_runs")
