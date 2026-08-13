"""Add restricted laboratory candidates for course offerings.

Revision ID: 0032
Revises: 0031
"""

from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_offering_allowed_laboratories",
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("laboratory_id", sa.Uuid(), nullable=False),
        sa.Column("preference_priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["laboratory_id"], ["laboratories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("course_offering_id", "laboratory_id"),
        sa.UniqueConstraint("course_offering_id", "laboratory_id", name="uq_course_offering_allowed_laboratory"),
        sa.CheckConstraint("preference_priority >= 1", name="ck_course_offering_allowed_laboratory_priority"),
    )
    op.create_index(
        "ix_course_offering_allowed_laboratories_laboratory_id",
        "course_offering_allowed_laboratories",
        ["laboratory_id"],
    )
    op.drop_constraint("ck_course_offering_laboratory_selection", "course_offerings", type_="check")
    op.create_check_constraint(
        "ck_course_offering_laboratory_selection",
        "course_offerings",
        "(laboratory_selection_mode = 'AUTO' AND laboratory_override_id IS NULL) OR "
        "(laboratory_selection_mode IN ('PREFERRED', 'FIXED') AND laboratory_override_id IS NOT NULL) OR "
        "(laboratory_selection_mode = 'RESTRICTED' AND laboratory_override_id IS NULL)",
    )


def downgrade() -> None:
    op.execute("UPDATE course_offerings SET laboratory_selection_mode = 'AUTO' WHERE laboratory_selection_mode = 'RESTRICTED'")
    op.drop_constraint("ck_course_offering_laboratory_selection", "course_offerings", type_="check")
    op.create_check_constraint(
        "ck_course_offering_laboratory_selection",
        "course_offerings",
        "(laboratory_selection_mode = 'AUTO' AND laboratory_override_id IS NULL) OR "
        "(laboratory_selection_mode IN ('PREFERRED', 'FIXED') AND laboratory_override_id IS NOT NULL)",
    )
    op.drop_index(
        "ix_course_offering_allowed_laboratories_laboratory_id",
        table_name="course_offering_allowed_laboratories",
    )
    op.drop_table("course_offering_allowed_laboratories")
