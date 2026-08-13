"""Add synchronized laboratory rotation groups and blocks.

Revision ID: 0026
Revises: 0025
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("laboratory_rotation_groups", sa.Column("section_id", sa.Uuid(), nullable=True))
    op.add_column("laboratory_rotation_groups", sa.Column("academic_term_id", sa.Uuid(), nullable=True))
    op.execute("""
        UPDATE laboratory_rotation_groups AS rotation_group
        SET section_id = configuration.section_id,
            academic_term_id = offering.academic_term_id
        FROM laboratory_batch_configurations AS configuration
        JOIN course_offerings AS offering ON offering.id = configuration.course_offering_id
        WHERE rotation_group.laboratory_batch_configuration_id = configuration.id
    """)
    op.alter_column("laboratory_rotation_groups", "section_id", nullable=False)
    op.alter_column("laboratory_rotation_groups", "academic_term_id", nullable=False)
    op.alter_column("laboratory_rotation_groups", "laboratory_batch_configuration_id", existing_type=sa.Uuid(), nullable=True)
    op.create_foreign_key("fk_rotation_group_section", "laboratory_rotation_groups", "sections", ["section_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_rotation_group_academic_term", "laboratory_rotation_groups", "academic_terms", ["academic_term_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_rotation_group_section", "laboratory_rotation_groups", ["section_id"])
    op.create_index("ix_rotation_group_academic_term", "laboratory_rotation_groups", ["academic_term_id"])
    op.create_index(
        "uq_active_rotation_group_code",
        "laboratory_rotation_groups",
        ["section_id", "academic_term_id", "rotation_code"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "laboratory_rotation_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rotation_group_id", sa.Uuid(), nullable=False),
        sa.Column("block_number", sa.Integer(), nullable=False),
        sa.Column("block_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["rotation_group_id"], ["laboratory_rotation_groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("rotation_group_id", "block_number", name="uq_rotation_block_number"),
        sa.CheckConstraint("block_number >= 1", name="ck_rotation_block_number_positive"),
    )
    op.create_index("ix_rotation_block_group", "laboratory_rotation_blocks", ["rotation_group_id"])

    op.add_column("laboratory_rotation_assignments", sa.Column("rotation_block_id", sa.Uuid(), nullable=True))
    op.add_column("laboratory_rotation_assignments", sa.Column("laboratory_id", sa.Uuid(), nullable=True))
    op.add_column("laboratory_rotation_assignments", sa.Column("main_faculty_id", sa.Uuid(), nullable=True))
    op.add_column("laboratory_rotation_assignments", sa.Column("supporting_faculty_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("laboratory_rotation_assignments", sa.Column("session_duration", sa.Integer(), nullable=True))

    # Preserve legacy assignments by turning each former position into a block.
    op.execute("""
        INSERT INTO laboratory_rotation_blocks (id, rotation_group_id, block_number, block_name, is_active)
        SELECT (md5(random()::text || clock_timestamp()::text || group_id::text || rotation_position::text))::uuid,
               group_id, rotation_position, 'Legacy Block ' || rotation_position, true
        FROM (
            SELECT DISTINCT rotation_group_id AS group_id, rotation_position
            FROM laboratory_rotation_assignments
        ) AS legacy
    """)
    op.execute("""
        UPDATE laboratory_rotation_assignments AS assignment
        SET rotation_block_id = block.id
        FROM laboratory_rotation_blocks AS block
        WHERE block.rotation_group_id = assignment.rotation_group_id
          AND block.block_number = assignment.rotation_position
    """)
    op.execute("""
        UPDATE laboratory_rotation_assignments AS assignment
        SET laboratory_id = course.default_laboratory_id,
            session_duration = course.lab_session_duration
        FROM course_offerings AS offering
        JOIN courses AS course ON course.id = offering.course_id
        WHERE assignment.course_offering_id = offering.id
    """)
    op.execute("""
        UPDATE laboratory_rotation_assignments AS assignment
        SET main_faculty_id = allocation.faculty_id
        FROM laboratory_faculty_allocations AS allocation
        WHERE allocation.course_offering_id = assignment.course_offering_id
          AND allocation.role_type = 'MAIN'
          AND allocation.is_active = true
          AND allocation.id = (
              SELECT candidate.id
              FROM laboratory_faculty_allocations AS candidate
              WHERE candidate.course_offering_id = assignment.course_offering_id
                AND candidate.role_type = 'MAIN'
                AND candidate.is_active = true
              ORDER BY candidate.id
              LIMIT 1
          )
    """)
    op.alter_column("laboratory_rotation_assignments", "rotation_block_id", nullable=False)

    op.execute("ALTER TABLE laboratory_rotation_assignments DROP CONSTRAINT IF EXISTS laboratory_rotation_assignments_rotation_group_id_batch_id_course_offering_id_key")
    op.execute("ALTER TABLE laboratory_rotation_assignments DROP CONSTRAINT IF EXISTS laboratory_rotation_assignments_rotation_group_id_rotation_position_key")
    op.execute("ALTER TABLE laboratory_rotation_assignments DROP CONSTRAINT IF EXISTS uq_rotation_assignment_combo")
    op.execute("ALTER TABLE laboratory_rotation_assignments DROP CONSTRAINT IF EXISTS uq_rotation_assignment_position")
    op.create_foreign_key("fk_rotation_assignment_block", "laboratory_rotation_assignments", "laboratory_rotation_blocks", ["rotation_block_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_rotation_assignment_laboratory", "laboratory_rotation_assignments", "laboratories", ["laboratory_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_rotation_assignment_main_faculty", "laboratory_rotation_assignments", "faculty", ["main_faculty_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_rotation_block_student_group", "laboratory_rotation_assignments", ["rotation_block_id", "batch_id"])
    op.create_unique_constraint("uq_rotation_block_offering", "laboratory_rotation_assignments", ["rotation_block_id", "course_offering_id"])
    op.create_unique_constraint("uq_rotation_block_position", "laboratory_rotation_assignments", ["rotation_block_id", "rotation_position"])
    op.create_check_constraint("ck_rotation_assignment_position_positive", "laboratory_rotation_assignments", "rotation_position >= 1")
    op.create_check_constraint("ck_rotation_assignment_session_duration", "laboratory_rotation_assignments", "session_duration IS NULL OR session_duration IN (2, 3)")
    op.create_index("ix_rotation_assignment_block", "laboratory_rotation_assignments", ["rotation_block_id"])
    op.create_index("ix_rotation_assignment_laboratory", "laboratory_rotation_assignments", ["laboratory_id"])
    op.create_index("ix_rotation_assignment_main_faculty", "laboratory_rotation_assignments", ["main_faculty_id"])

    op.add_column("timetable_entries", sa.Column("laboratory_rotation_block_id", sa.Uuid(), nullable=True))
    op.add_column("timetable_entries", sa.Column("laboratory_rotation_assignment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_timetable_entry_rotation_block", "timetable_entries", "laboratory_rotation_blocks", ["laboratory_rotation_block_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_timetable_entry_rotation_assignment", "timetable_entries", "laboratory_rotation_assignments", ["laboratory_rotation_assignment_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_timetable_entry_rotation_block", "timetable_entries", ["laboratory_rotation_block_id"])
    op.create_index("ix_timetable_entry_rotation_assignment", "timetable_entries", ["laboratory_rotation_assignment_id"])


def downgrade() -> None:
    op.drop_index("ix_timetable_entry_rotation_assignment", table_name="timetable_entries")
    op.drop_index("ix_timetable_entry_rotation_block", table_name="timetable_entries")
    op.drop_constraint("fk_timetable_entry_rotation_assignment", "timetable_entries", type_="foreignkey")
    op.drop_constraint("fk_timetable_entry_rotation_block", "timetable_entries", type_="foreignkey")
    op.drop_column("timetable_entries", "laboratory_rotation_assignment_id")
    op.drop_column("timetable_entries", "laboratory_rotation_block_id")

    op.drop_index("ix_rotation_assignment_main_faculty", table_name="laboratory_rotation_assignments")
    op.drop_index("ix_rotation_assignment_laboratory", table_name="laboratory_rotation_assignments")
    op.drop_index("ix_rotation_assignment_block", table_name="laboratory_rotation_assignments")
    op.drop_constraint("ck_rotation_assignment_session_duration", "laboratory_rotation_assignments", type_="check")
    op.drop_constraint("ck_rotation_assignment_position_positive", "laboratory_rotation_assignments", type_="check")
    op.drop_constraint("uq_rotation_block_position", "laboratory_rotation_assignments", type_="unique")
    op.drop_constraint("uq_rotation_block_offering", "laboratory_rotation_assignments", type_="unique")
    op.drop_constraint("uq_rotation_block_student_group", "laboratory_rotation_assignments", type_="unique")
    op.drop_constraint("fk_rotation_assignment_main_faculty", "laboratory_rotation_assignments", type_="foreignkey")
    op.drop_constraint("fk_rotation_assignment_laboratory", "laboratory_rotation_assignments", type_="foreignkey")
    op.drop_constraint("fk_rotation_assignment_block", "laboratory_rotation_assignments", type_="foreignkey")
    op.drop_column("laboratory_rotation_assignments", "session_duration")
    op.drop_column("laboratory_rotation_assignments", "supporting_faculty_ids")
    op.drop_column("laboratory_rotation_assignments", "main_faculty_id")
    op.drop_column("laboratory_rotation_assignments", "laboratory_id")
    op.drop_column("laboratory_rotation_assignments", "rotation_block_id")
    op.create_unique_constraint("uq_rotation_assignment_combo", "laboratory_rotation_assignments", ["rotation_group_id", "batch_id", "course_offering_id"])
    op.create_unique_constraint("uq_rotation_assignment_position", "laboratory_rotation_assignments", ["rotation_group_id", "rotation_position"])

    op.drop_index("ix_rotation_block_group", table_name="laboratory_rotation_blocks")
    op.drop_table("laboratory_rotation_blocks")
    op.drop_index("uq_active_rotation_group_code", table_name="laboratory_rotation_groups")
    op.drop_index("ix_rotation_group_academic_term", table_name="laboratory_rotation_groups")
    op.drop_index("ix_rotation_group_section", table_name="laboratory_rotation_groups")
    op.drop_constraint("fk_rotation_group_academic_term", "laboratory_rotation_groups", type_="foreignkey")
    op.drop_constraint("fk_rotation_group_section", "laboratory_rotation_groups", type_="foreignkey")
    op.drop_column("laboratory_rotation_groups", "academic_term_id")
    op.drop_column("laboratory_rotation_groups", "section_id")
    op.alter_column("laboratory_rotation_groups", "laboratory_batch_configuration_id", existing_type=sa.Uuid(), nullable=False)
