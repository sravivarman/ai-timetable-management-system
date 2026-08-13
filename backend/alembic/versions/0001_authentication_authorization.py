"""Create authentication and authorization tables with initial system roles.

Revision ID: 0001
Revises:
Create Date: 2026-07-31
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


ADMINISTRATOR_ID = UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35")
ROLES_MANAGE_ID = UUID("fd1cb765-21e6-5c1b-bfd7-02fa7dbf413c")
USERS_MANAGE_ID = UUID("35ae7a5d-41bb-5e34-bd26-262a601b25f6")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    roles = op.bulk_insert(
        sa.table("roles", sa.column("id", sa.Uuid()), sa.column("name", sa.String()), sa.column("description", sa.Text())),
        [
            {"id": ADMINISTRATOR_ID, "name": "Administrator", "description": "Full system administration"},
            {"id": UUID("e2365f15-2c14-5e9c-aed0-bb515a72194f"), "name": "Principal", "description": "Institution principal"},
            {"id": UUID("84c7d4e3-c1bd-50d6-aa5b-1a1bb3a7132d"), "name": "Dean", "description": "Academic dean"},
            {"id": UUID("b38de217-e739-55e9-840a-fd568ff18dc5"), "name": "HOD", "description": "Head of department"},
            {"id": UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f"), "name": "Timetable Coordinator", "description": "Timetable operations coordinator"},
            {"id": UUID("6d65e1bd-75ef-5b36-9730-a1b7c77c99d4"), "name": "Faculty", "description": "Faculty member"},
            {"id": UUID("c62bb1eb-3a06-5b78-86c0-d6f0f755a1c4"), "name": "Student", "description": "Student"},
        ],
    )
    op.bulk_insert(
        sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("resource", sa.String()), sa.column("action", sa.String()), sa.column("description", sa.Text())),
        [
            {"id": ROLES_MANAGE_ID, "resource": "roles", "action": "manage", "description": "Create, read, update, and delete roles"},
            {"id": USERS_MANAGE_ID, "resource": "users", "action": "manage", "description": "Create, read, update, and delete users"},
        ],
    )
    op.bulk_insert(
        sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())),
        [
            {"role_id": ADMINISTRATOR_ID, "permission_id": ROLES_MANAGE_ID},
            {"role_id": ADMINISTRATOR_ID, "permission_id": USERS_MANAGE_ID},
        ],
    )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
