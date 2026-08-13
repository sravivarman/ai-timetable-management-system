"""Create course offerings.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_offerings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("academic_term_id", sa.Uuid(), nullable=False),
        sa.Column("weekly_periods_override", sa.Integer()),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("elective_group_name", sa.String(255)),
        sa.Column("common_theory_group_code", sa.String(100)),
        sa.Column("is_common_theory", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("course_id", "section_id", "academic_term_id", name="uq_course_offering_course_section_term"),
        sa.CheckConstraint("weekly_periods_override IS NULL OR weekly_periods_override > 0", name="ck_course_offerings_periods_override_positive"),
    )
    for column in ("course_id", "section_id", "academic_term_id", "common_theory_group_code"):
        op.create_index(f"ix_course_offerings_{column}", "course_offerings", [column])


def downgrade() -> None:
    for column in ("common_theory_group_code", "academic_term_id", "section_id", "course_id"):
        op.drop_index(f"ix_course_offerings_{column}", table_name="course_offerings")
    op.drop_table("course_offerings")
