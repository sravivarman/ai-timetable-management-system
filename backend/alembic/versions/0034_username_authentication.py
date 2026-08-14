"""Add case-insensitive usernames for authentication.

Revision ID: 0034
Revises: 0033
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def _candidate(email: str) -> str:
    local = email.partition("@")[0].strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "", local) or "user"
    return value[:100]


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=100), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, email FROM users ORDER BY created_at, id")).mappings().all()
    used: set[str] = set()
    for row in rows:
        user_id = str(row["id"])
        email = str(row["email"])
        base = "administrator" if email.strip().lower() == "admin@vce.ac.in" else _candidate(email)
        if base == "administrator" and email.strip().lower() != "admin@vce.ac.in":
            base = f"administrator-{user_id.replace('-', '')[:8]}"
        username = base
        counter = 1
        while username.lower() in used:
            suffix = user_id.replace("-", "")[:8] if counter == 1 else f"{user_id.replace('-', '')[:8]}-{counter}"
            username = f"{base[:99-len(suffix)]}-{suffix}"
            counter += 1
        used.add(username.lower())
        connection.execute(sa.text("UPDATE users SET username = :username WHERE id = :user_id"), {"username": username, "user_id": row["id"]})
    op.alter_column("users", "username", existing_type=sa.String(length=100), nullable=False)
    op.create_index("uq_users_username_ci", "users", [sa.text("lower(username)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_username_ci", table_name="users")
    op.drop_column("users", "username")
