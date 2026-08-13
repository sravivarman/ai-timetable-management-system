"""Add explicit course laboratory eligibility and offering overrides.

Revision ID: 0031
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_eligible_laboratories",
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("laboratory_id", sa.Uuid(), nullable=False),
        sa.Column("preference_priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["laboratory_id"], ["laboratories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("course_id", "laboratory_id"),
        sa.UniqueConstraint("course_id", "laboratory_id", name="uq_course_eligible_laboratory"),
        sa.CheckConstraint("preference_priority >= 1", name="ck_course_eligible_laboratory_priority"),
    )
    op.create_index("ix_course_eligible_laboratories_laboratory_id", "course_eligible_laboratories", ["laboratory_id"])
    op.execute(
        """
        INSERT INTO course_eligible_laboratories
            (course_id, laboratory_id, preference_priority, is_active)
        SELECT id, default_laboratory_id, 1, TRUE
        FROM courses
        WHERE default_laboratory_id IS NOT NULL
        ON CONFLICT (course_id, laboratory_id) DO NOTHING
        """
    )
    op.add_column("course_offerings", sa.Column("laboratory_selection_mode", sa.String(length=20), nullable=False, server_default="AUTO"))
    op.add_column("course_offerings", sa.Column("laboratory_override_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_course_offerings_laboratory_override", "course_offerings", "laboratories", ["laboratory_override_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_course_offerings_laboratory_selection_mode", "course_offerings", ["laboratory_selection_mode"])
    op.create_index("ix_course_offerings_laboratory_override_id", "course_offerings", ["laboratory_override_id"])
    op.create_check_constraint(
        "ck_course_offering_laboratory_selection",
        "course_offerings",
        "(laboratory_selection_mode = 'AUTO' AND laboratory_override_id IS NULL) OR "
        "(laboratory_selection_mode IN ('PREFERRED', 'FIXED') AND laboratory_override_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_course_offering_laboratory_selection", "course_offerings", type_="check")
    op.drop_index("ix_course_offerings_laboratory_override_id", table_name="course_offerings")
    op.drop_index("ix_course_offerings_laboratory_selection_mode", table_name="course_offerings")
    op.drop_constraint("fk_course_offerings_laboratory_override", "course_offerings", type_="foreignkey")
    op.drop_column("course_offerings", "laboratory_override_id")
    op.drop_column("course_offerings", "laboratory_selection_mode")
    op.drop_index("ix_course_eligible_laboratories_laboratory_id", table_name="course_eligible_laboratories")
    op.drop_table("course_eligible_laboratories")
