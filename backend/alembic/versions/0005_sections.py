"""Create sections and grant section permissions.

Revision ID: 0005
Revises: 0004
"""
from uuid import UUID
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None
ADMINISTRATOR_ID = UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35")
TIMETABLE_COORDINATOR_ID = UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f")
SECTIONS_READ_ID = UUID("b2639645-9cb8-5272-8c73-3822aeecdda0")
SECTIONS_MANAGE_ID = UUID("8ea68492-8c60-5b4a-9323-9f254ad2af42")

def upgrade() -> None:
    op.create_table("sections", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("program_id", sa.Uuid(), nullable=False), sa.Column("academic_term_id", sa.Uuid(), nullable=False), sa.Column("section_name", sa.String(length=20), nullable=False), sa.Column("section_code", sa.String(length=60), nullable=False), sa.Column("student_strength", sa.Integer(), nullable=False), sa.Column("primary_classroom_id", sa.Uuid(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["academic_term_id"], ["academic_terms.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("program_id", "academic_term_id", "section_name", name="uq_sections_program_term_name"), sa.UniqueConstraint("program_id", "academic_term_id", "section_code", name="uq_sections_program_term_code"))
    op.create_index("ix_sections_program_id", "sections", ["program_id"]); op.create_index("ix_sections_academic_term_id", "sections", ["academic_term_id"])
    op.bulk_insert(sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("resource", sa.String()), sa.column("action", sa.String()), sa.column("description", sa.Text())), [{"id": SECTIONS_READ_ID, "resource": "sections", "action": "read", "description": "View sections"}, {"id": SECTIONS_MANAGE_ID, "resource": "sections", "action": "manage", "description": "Create, update, delete, and restore sections"}])
    op.bulk_insert(sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())), [{"role_id": ADMINISTRATOR_ID, "permission_id": SECTIONS_READ_ID}, {"role_id": ADMINISTRATOR_ID, "permission_id": SECTIONS_MANAGE_ID}, {"role_id": TIMETABLE_COORDINATOR_ID, "permission_id": SECTIONS_READ_ID}])

def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN ('b2639645-9cb8-5272-8c73-3822aeecdda0', '8ea68492-8c60-5b4a-9323-9f254ad2af42')")); op.execute(sa.text("DELETE FROM permissions WHERE id IN ('b2639645-9cb8-5272-8c73-3822aeecdda0', '8ea68492-8c60-5b4a-9323-9f254ad2af42')")); op.drop_index("ix_sections_academic_term_id", table_name="sections"); op.drop_index("ix_sections_program_id", table_name="sections"); op.drop_table("sections")
