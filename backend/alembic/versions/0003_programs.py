"""Create programs and grant program permissions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


ADMINISTRATOR_ID = UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35")
TIMETABLE_COORDINATOR_ID = UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f")
PROGRAMS_READ_ID = UUID("c72566b4-319e-5cf3-977f-623794162173")
PROGRAMS_MANAGE_ID = UUID("b45018e2-8822-5f1f-acac-97d2da9ad138")


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("program_code", sa.String(length=30), nullable=False),
        sa.Column("program_name", sa.String(length=255), nullable=False),
        sa.Column("degree_type", sa.String(length=10), nullable=False),
        sa.Column("duration_years", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programs_department_id", "programs", ["department_id"], unique=False)
    op.create_index("ix_programs_program_code", "programs", ["program_code"], unique=True)

    op.bulk_insert(
        sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("resource", sa.String()), sa.column("action", sa.String()), sa.column("description", sa.Text())),
        [
            {"id": PROGRAMS_READ_ID, "resource": "programs", "action": "read", "description": "View programs"},
            {"id": PROGRAMS_MANAGE_ID, "resource": "programs", "action": "manage", "description": "Create, update, delete, and restore programs"},
        ],
    )
    op.bulk_insert(
        sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())),
        [
            {"role_id": ADMINISTRATOR_ID, "permission_id": PROGRAMS_READ_ID},
            {"role_id": ADMINISTRATOR_ID, "permission_id": PROGRAMS_MANAGE_ID},
            {"role_id": TIMETABLE_COORDINATOR_ID, "permission_id": PROGRAMS_READ_ID},
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN ('c72566b4-319e-5cf3-977f-623794162173', 'b45018e2-8822-5f1f-acac-97d2da9ad138')"))
    op.execute(sa.text("DELETE FROM permissions WHERE id IN ('c72566b4-319e-5cf3-977f-623794162173', 'b45018e2-8822-5f1f-acac-97d2da9ad138')"))
    op.drop_index("ix_programs_program_code", table_name="programs")
    op.drop_index("ix_programs_department_id", table_name="programs")
    op.drop_table("programs")
