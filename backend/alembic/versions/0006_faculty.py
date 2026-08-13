"""Create faculty and grant faculty permissions.

Revision ID: 0006
Revises: 0005
"""
from uuid import UUID
from alembic import op
import sqlalchemy as sa
revision="0006"; down_revision="0005"; branch_labels=None; depends_on=None
ADMIN=UUID("a71e7ba0-1e43-5c51-9554-72efa7ee3c35"); TTC=UUID("6ea2c6f7-5c20-5bda-9832-bfd93e82734f"); HOD=UUID("b38de217-e739-55e9-840a-fd568ff18dc5"); READ=UUID("09de2012-bb42-57b5-a930-f4f8ddad5690"); MANAGE=UUID("bcb9e8be-0719-5e90-9f47-fb76d4772fc5")
def upgrade():
    op.create_table("faculty",sa.Column("id",sa.Uuid(),nullable=False),sa.Column("faculty_code",sa.String(30),nullable=False),sa.Column("full_name",sa.String(255),nullable=False),sa.Column("department_id",sa.Uuid(),nullable=False),sa.Column("designation",sa.String(50),nullable=False),sa.Column("institutional_email",sa.String(320),nullable=False),sa.Column("phone_number",sa.String(30)),sa.Column("user_id",sa.Uuid()),sa.Column("minimum_weekly_workload",sa.Integer(),nullable=False),sa.Column("maximum_weekly_workload",sa.Integer(),nullable=False),sa.Column("maximum_periods_per_day",sa.Integer()),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.ForeignKeyConstraint(["department_id"],["departments.id"],ondelete="RESTRICT"),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="SET NULL"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("user_id"))
    op.create_index("ix_faculty_faculty_code","faculty",["faculty_code"],unique=True); op.create_index("ix_faculty_institutional_email","faculty",["institutional_email"],unique=True); op.create_index("ix_faculty_department_id","faculty",["department_id"])
    op.bulk_insert(sa.table("permissions",sa.column("id",sa.Uuid()),sa.column("resource",sa.String()),sa.column("action",sa.String()),sa.column("description",sa.Text())),[{"id":READ,"resource":"faculty","action":"read","description":"View faculty"},{"id":MANAGE,"resource":"faculty","action":"manage","description":"Manage faculty"}])
    op.bulk_insert(sa.table("role_permissions",sa.column("role_id",sa.Uuid()),sa.column("permission_id",sa.Uuid())),[{"role_id":ADMIN,"permission_id":READ},{"role_id":ADMIN,"permission_id":MANAGE},{"role_id":TTC,"permission_id":READ},{"role_id":HOD,"permission_id":READ}])
def downgrade():
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN ('09de2012-bb42-57b5-a930-f4f8ddad5690','bcb9e8be-0719-5e90-9f47-fb76d4772fc5')"));op.execute(sa.text("DELETE FROM permissions WHERE id IN ('09de2012-bb42-57b5-a930-f4f8ddad5690','bcb9e8be-0719-5e90-9f47-fb76d4772fc5')"));op.drop_index("ix_faculty_department_id",table_name="faculty");op.drop_index("ix_faculty_institutional_email",table_name="faculty");op.drop_index("ix_faculty_faculty_code",table_name="faculty");op.drop_table("faculty")
