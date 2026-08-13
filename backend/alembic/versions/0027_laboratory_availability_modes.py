"""Add generic laboratory availability modes and typed availability slots.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "laboratories",
        sa.Column("availability_mode", sa.String(length=24), nullable=True, server_default="ALL_PERIODS"),
    )
    # A legacy row with any stored block was effectively EXCEPT_BLOCKED even
    # when the old checkbox retained its default true value. Preserve that
    # effective behavior; all other true rows migrate to ALL_PERIODS.
    op.execute(sa.text("""
        UPDATE laboratories AS laboratory
        SET availability_mode = CASE
            WHEN EXISTS (
                SELECT 1 FROM laboratory_availability_blocks AS slot
                WHERE slot.laboratory_id = laboratory.id
            ) THEN 'EXCEPT_BLOCKED'
            WHEN laboratory.is_available_all_periods THEN 'ALL_PERIODS'
            ELSE 'EXCEPT_BLOCKED'
        END
    """))
    op.execute("UPDATE laboratories SET is_available_all_periods = (availability_mode = 'ALL_PERIODS')")
    op.alter_column("laboratories", "availability_mode", nullable=False, server_default="ALL_PERIODS")
    op.create_check_constraint(
        "ck_laboratories_availability_mode",
        "laboratories",
        "availability_mode IN ('ALL_PERIODS','EXCEPT_BLOCKED','ONLY_SELECTED')",
    )

    op.add_column(
        "laboratory_availability_blocks",
        sa.Column("availability_type", sa.String(length=12), nullable=True, server_default="BLOCKED"),
    )
    op.execute("UPDATE laboratory_availability_blocks SET availability_type = 'BLOCKED' WHERE availability_type IS NULL")
    op.alter_column("laboratory_availability_blocks", "availability_type", nullable=False, server_default="BLOCKED")
    op.create_check_constraint(
        "ck_laboratory_availability_type",
        "laboratory_availability_blocks",
        "availability_type IN ('BLOCKED','ALLOWED')",
    )
    # Soft-deleted slots are history and must not prevent a new active slot at
    # the same day/period. The previous full-table unique constraint made
    # mode changes impossible without physically deleting history.
    # Migration 0016 created this constraint without a name, so PostgreSQL's
    # generated (and possibly truncated) name is installation-dependent.
    op.execute(sa.text("""
        DO $$
        DECLARE constraint_name text;
        BEGIN
          SELECT constraint_row.conname INTO constraint_name
          FROM pg_constraint AS constraint_row
          JOIN pg_class AS table_row ON table_row.oid = constraint_row.conrelid
          WHERE table_row.relname = 'laboratory_availability_blocks'
            AND constraint_row.contype = 'u'
            AND (
              SELECT array_agg(attribute_row.attname::text ORDER BY key_row.ordinality)
              FROM unnest(constraint_row.conkey) WITH ORDINALITY AS key_row(attnum, ordinality)
              JOIN pg_attribute AS attribute_row
                ON attribute_row.attrelid = table_row.oid
               AND attribute_row.attnum = key_row.attnum
            ) = ARRAY['laboratory_id','academic_term_id','working_day_id','period_number'];
          IF constraint_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE laboratory_availability_blocks DROP CONSTRAINT %I', constraint_name);
          END IF;
        END $$;
    """))
    op.create_index(
        "uq_laboratory_active_availability_slot",
        "laboratory_availability_blocks",
        ["laboratory_id", "academic_term_id", "working_day_id", "period_number"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade():
    op.drop_index("uq_laboratory_active_availability_slot", table_name="laboratory_availability_blocks")
    # A database containing repeated historical slots cannot restore the old
    # full-table uniqueness without data loss, so downgrade fails clearly.
    op.create_unique_constraint(
        "uq_laboratory_block_slot",
        "laboratory_availability_blocks",
        ["laboratory_id", "academic_term_id", "working_day_id", "period_number"],
    )
    op.drop_constraint("ck_laboratory_availability_type", "laboratory_availability_blocks", type_="check")
    op.drop_column("laboratory_availability_blocks", "availability_type")
    op.drop_constraint("ck_laboratories_availability_mode", "laboratories", type_="check")
    op.drop_column("laboratories", "availability_mode")
