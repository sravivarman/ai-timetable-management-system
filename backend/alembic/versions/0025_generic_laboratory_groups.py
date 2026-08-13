"""Generalize laboratory batches into arbitrary student groups.

Revision ID: 0025
Revises: 0024
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original check was unnamed, so PostgreSQL generated this name.
    op.execute(
        "ALTER TABLE laboratory_batch_configurations "
        "DROP CONSTRAINT IF EXISTS laboratory_batch_configurations_number_of_batches_check"
    )
    op.alter_column(
        "laboratory_batch_configurations",
        "number_of_batches",
        new_column_name="number_of_groups",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.add_column(
        "laboratory_batch_configurations",
        sa.Column(
            "group_naming_pattern",
            sa.String(length=100),
            nullable=False,
            server_default=sa.text("'{section}{sequence}'"),
        ),
    )
    op.create_check_constraint(
        "ck_laboratory_batch_configurations_group_count_positive",
        "laboratory_batch_configurations",
        "number_of_groups >= 1",
    )

    op.alter_column(
        "courses",
        "lab_batch_count",
        new_column_name="default_lab_group_count",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "ck_courses_default_lab_group_count_positive",
        "courses",
        "default_lab_group_count IS NULL OR default_lab_group_count >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_courses_default_lab_group_count_positive",
        "courses",
        type_="check",
    )
    op.alter_column(
        "courses",
        "default_lab_group_count",
        new_column_name="lab_batch_count",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )

    op.drop_constraint(
        "ck_laboratory_batch_configurations_group_count_positive",
        "laboratory_batch_configurations",
        type_="check",
    )
    op.drop_column("laboratory_batch_configurations", "group_naming_pattern")
    op.alter_column(
        "laboratory_batch_configurations",
        "number_of_groups",
        new_column_name="number_of_batches",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    # The former IN (1, 2, 3) constraint is deliberately not restored: rows
    # using larger group counts must remain downgrade-safe and data-preserving.
