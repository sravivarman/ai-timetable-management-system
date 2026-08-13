"""Create course master table.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_code", sa.String(50), nullable=False, unique=True),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("offering_department_id", sa.Uuid(), nullable=False),
        sa.Column("course_type", sa.String(30), nullable=False),
        sa.Column("elective_type", sa.String(30)),
        sa.Column("weekly_periods", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Numeric(5, 2)),
        sa.Column("allows_same_course_double_period", sa.Boolean(), nullable=False),
        sa.Column("lab_session_duration", sa.Integer()),
        sa.Column("lab_sessions_per_week", sa.Integer()),
        sa.Column("lab_batch_count", sa.Integer()),
        sa.Column("default_laboratory_id", sa.Uuid()),
        sa.Column("counts_toward_workload", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["offering_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["default_laboratory_id"], ["laboratories.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("weekly_periods > 0", name="ck_courses_weekly_periods_positive"),
        sa.CheckConstraint("credits IS NULL OR credits >= 0", name="ck_courses_credits_nonnegative"),
    )
    op.create_index("ix_courses_offering_department_id", "courses", ["offering_department_id"])
    op.create_index("ix_courses_course_type", "courses", ["course_type"])
    op.create_index("ix_courses_elective_type", "courses", ["elective_type"])


def downgrade() -> None:
    op.drop_index("ix_courses_elective_type", table_name="courses")
    op.drop_index("ix_courses_course_type", table_name="courses")
    op.drop_index("ix_courses_offering_department_id", table_name="courses")
    op.drop_table("courses")
