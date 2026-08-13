"""Create academic terms and grant academic-term permissions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-01
"""

from uuid import UUID
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ADMINISTRATOR_ID = UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35")
TIMETABLE_COORDINATOR_ID = UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f")
TERMS_READ_ID = UUID("a4b620b2-4264-538e-bc83-21c57b7a777d")
TERMS_MANAGE_ID = UUID("f43e3e45-80e4-5afd-92b5-d32f6e7a08e9")


def upgrade() -> None:
    op.create_table("academic_terms", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("academic_year", sa.String(length=9), nullable=False), sa.Column("term_name", sa.String(length=10), nullable=False), sa.Column("year_number", sa.Integer(), nullable=False), sa.Column("semester_number", sa.Integer(), nullable=False), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("is_current", sa.Boolean(), nullable=False), sa.Column("is_first_year_term", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("uq_active_academic_terms_year_semester", "academic_terms", ["academic_year", "year_number", "semester_number"], unique=True, postgresql_where=sa.text("is_active"))
    op.bulk_insert(sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("resource", sa.String()), sa.column("action", sa.String()), sa.column("description", sa.Text())), [{"id": TERMS_READ_ID, "resource": "academic_terms", "action": "read", "description": "View academic terms"}, {"id": TERMS_MANAGE_ID, "resource": "academic_terms", "action": "manage", "description": "Create, update, delete, and restore academic terms"}])
    op.bulk_insert(sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())), [{"role_id": ADMINISTRATOR_ID, "permission_id": TERMS_READ_ID}, {"role_id": ADMINISTRATOR_ID, "permission_id": TERMS_MANAGE_ID}, {"role_id": TIMETABLE_COORDINATOR_ID, "permission_id": TERMS_READ_ID}])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN ('a4b620b2-4264-538e-bc83-21c57b7a777d', 'f43e3e45-80e4-5afd-92b5-d32f6e7a08e9')"))
    op.execute(sa.text("DELETE FROM permissions WHERE id IN ('a4b620b2-4264-538e-bc83-21c57b7a777d', 'f43e3e45-80e4-5afd-92b5-d32f6e7a08e9')"))
    op.drop_index("uq_active_academic_terms_year_semester", table_name="academic_terms")
    op.drop_table("academic_terms")
