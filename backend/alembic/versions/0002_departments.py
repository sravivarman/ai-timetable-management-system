"""Create departments and grant department permissions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-01
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


ADMINISTRATOR_ID = UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35")
TIMETABLE_COORDINATOR_ID = UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f")
DEPARTMENTS_VIEW_ID = UUID("fa19db3a-dc0c-59ba-a9f2-c932367c4f89")
DEPARTMENTS_MANAGE_ID = UUID("505a740d-a7a8-5736-943a-7395415f34f0")


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_code", sa.String(length=20), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_departments_department_code", "departments", ["department_code"], unique=True)

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permissions,
        [
            {"id": DEPARTMENTS_VIEW_ID, "resource": "departments", "action": "view", "description": "View departments"},
            {"id": DEPARTMENTS_MANAGE_ID, "resource": "departments", "action": "manage", "description": "Create, update, delete, and restore departments"},
        ],
    )
    op.bulk_insert(
        sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())),
        [
            {"role_id": ADMINISTRATOR_ID, "permission_id": DEPARTMENTS_VIEW_ID},
            {"role_id": ADMINISTRATOR_ID, "permission_id": DEPARTMENTS_MANAGE_ID},
            {"role_id": TIMETABLE_COORDINATOR_ID, "permission_id": DEPARTMENTS_VIEW_ID},
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN ('fa19db3a-dc0c-59ba-a9f2-c932367c4f89', '505a740d-a7a8-5736-943a-7395415f34f0')"))
    op.execute(sa.text("DELETE FROM permissions WHERE id IN ('fa19db3a-dc0c-59ba-a9f2-c932367c4f89', '505a740d-a7a8-5736-943a-7395415f34f0')"))
    op.drop_index("ix_departments_department_code", table_name="departments")
    op.drop_table("departments")
