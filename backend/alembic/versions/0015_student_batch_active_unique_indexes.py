"""Allow historical student batches with reused active names.
Revision ID: 0015
Revises: 0014
"""
from alembic import op
revision="0015";down_revision="0014";branch_labels=None;depends_on=None
def upgrade():
 op.drop_constraint("student_batches_section_id_batch_name_key","student_batches",type_="unique")
 op.drop_constraint("student_batches_section_id_sequence_number_key","student_batches",type_="unique")
 op.create_index("uq_active_batch_section_name","student_batches",["section_id","batch_name"],unique=True,postgresql_where=__import__("sqlalchemy").text("is_active"))
 op.create_index("uq_active_batch_section_sequence","student_batches",["section_id","sequence_number"],unique=True,postgresql_where=__import__("sqlalchemy").text("is_active"))
def downgrade():
 op.drop_index("uq_active_batch_section_sequence",table_name="student_batches");op.drop_index("uq_active_batch_section_name",table_name="student_batches")
 op.create_unique_constraint("student_batches_section_id_batch_name_key","student_batches",["section_id","batch_name"])
 op.create_unique_constraint("student_batches_section_id_sequence_number_key","student_batches",["section_id","sequence_number"])
