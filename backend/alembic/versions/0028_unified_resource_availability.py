"""Generalize availability into registry-driven resource profiles and slots.

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa

revision="0028"
down_revision="0027"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        "resource_availability_profiles",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("resource_type",sa.String(40),nullable=False),
        sa.Column("resource_id",sa.Uuid(),nullable=False),
        sa.Column("academic_term_id",sa.Uuid(),nullable=False),
        sa.Column("availability_mode",sa.String(24),nullable=False,server_default="ALL_PERIODS"),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["academic_term_id"],["academic_terms.id"],ondelete="RESTRICT"),
        sa.CheckConstraint("availability_mode IN ('ALL_PERIODS','EXCEPT_BLOCKED','ONLY_SELECTED')",name="ck_resource_availability_profile_mode"),
    )
    op.create_index("ix_resource_availability_profiles_resource_type","resource_availability_profiles",["resource_type"])
    op.create_index("ix_resource_availability_profiles_resource_id","resource_availability_profiles",["resource_id"])
    op.create_index("ix_resource_availability_profiles_academic_term_id","resource_availability_profiles",["academic_term_id"])
    op.create_index("uq_active_resource_availability_profile","resource_availability_profiles",["resource_type","resource_id","academic_term_id"],unique=True,postgresql_where=sa.text("is_active"))

    op.rename_table("laboratory_availability_blocks","resource_availability_slots")
    op.alter_column("resource_availability_slots","laboratory_id",new_column_name="resource_id")
    op.add_column("resource_availability_slots",sa.Column("resource_type",sa.String(40),nullable=True,server_default="LABORATORY"))
    op.execute("UPDATE resource_availability_slots SET resource_type='LABORATORY' WHERE resource_type IS NULL")
    op.alter_column("resource_availability_slots","resource_type",nullable=False,server_default="LABORATORY")
    op.execute(sa.text("""
      DO $$ DECLARE constraint_name text; BEGIN
        SELECT constraint_row.conname INTO constraint_name
        FROM pg_constraint constraint_row
        JOIN pg_class table_row ON table_row.oid=constraint_row.conrelid
        JOIN pg_class referenced_row ON referenced_row.oid=constraint_row.confrelid
        WHERE table_row.relname='resource_availability_slots'
          AND referenced_row.relname='laboratories'
          AND constraint_row.contype='f' LIMIT 1;
        IF constraint_name IS NOT NULL THEN
          EXECUTE format('ALTER TABLE resource_availability_slots DROP CONSTRAINT %I',constraint_name);
        END IF;
      END $$;
    """))
    op.drop_index("uq_laboratory_active_availability_slot",table_name="resource_availability_slots")
    op.drop_constraint("ck_laboratory_availability_type","resource_availability_slots",type_="check")
    op.create_check_constraint("ck_resource_availability_slot_type","resource_availability_slots","availability_type IN ('BLOCKED','ALLOWED')")
    op.create_index("ix_resource_availability_slots_resource_type","resource_availability_slots",["resource_type"])
    op.create_index("ix_resource_availability_slots_resource_id","resource_availability_slots",["resource_id"])
    op.create_index("uq_active_resource_availability_slot","resource_availability_slots",["resource_type","resource_id","academic_term_id","working_day_id","period_number"],unique=True,postgresql_where=sa.text("is_active"))

    # Existing laboratory rows become generic slots, with one term-specific
    # profile per migrated laboratory/term pair.
    op.execute(sa.text("""
      INSERT INTO resource_availability_profiles
        (id,resource_type,resource_id,academic_term_id,availability_mode,is_active,created_at,updated_at)
      SELECT md5(slot.resource_id::text || slot.academic_term_id::text || 'LABORATORY')::uuid,
             'LABORATORY',slot.resource_id,slot.academic_term_id,laboratory.availability_mode,true,now(),now()
      FROM resource_availability_slots slot
      JOIN laboratories laboratory ON laboratory.id=slot.resource_id
      GROUP BY slot.resource_id,slot.academic_term_id,laboratory.availability_mode;
    """))

    # Existing hard faculty unavailability is translated once. Preferred and
    # avoid rows remain in the faculty soft-constraint model.
    op.execute(sa.text("""
      INSERT INTO resource_availability_slots
        (id,resource_type,resource_id,academic_term_id,working_day_id,period_number,availability_type,reason,is_active,created_at,updated_at)
      SELECT md5(availability.id::text || 'FACULTY')::uuid,'FACULTY',availability.faculty_id,
             availability.academic_term_id,day.id,availability.period_number,'BLOCKED',availability.reason,
             availability.is_active,COALESCE(availability.created_at,now()),COALESCE(availability.updated_at,now())
      FROM faculty_availability availability
      JOIN working_days day ON day.day_name=availability.day_of_week
      WHERE availability.availability_type='unavailable'
      ON CONFLICT DO NOTHING;
    """))
    op.execute(sa.text("""
      INSERT INTO resource_availability_profiles
        (id,resource_type,resource_id,academic_term_id,availability_mode,is_active,created_at,updated_at)
      SELECT md5(slot.resource_id::text || slot.academic_term_id::text || 'FACULTY')::uuid,
             'FACULTY',slot.resource_id,slot.academic_term_id,'EXCEPT_BLOCKED',true,now(),now()
      FROM resource_availability_slots slot WHERE slot.resource_type='FACULTY'
      GROUP BY slot.resource_id,slot.academic_term_id
      ON CONFLICT DO NOTHING;
    """))


def downgrade():
    # Non-laboratory profiles/slots can contain new data after this migration;
    # silently deleting them would violate the no-data-loss contract.
    op.execute(sa.text("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM resource_availability_slots WHERE resource_type<>'LABORATORY')
           OR EXISTS (SELECT 1 FROM resource_availability_profiles WHERE resource_type<>'LABORATORY') THEN
          RAISE EXCEPTION 'Cannot downgrade unified availability while non-laboratory data exists';
        END IF;
      END $$;
    """))
    op.drop_index("uq_active_resource_availability_slot",table_name="resource_availability_slots")
    op.drop_index("ix_resource_availability_slots_resource_id",table_name="resource_availability_slots")
    op.drop_index("ix_resource_availability_slots_resource_type",table_name="resource_availability_slots")
    op.drop_constraint("ck_resource_availability_slot_type","resource_availability_slots",type_="check")
    op.create_check_constraint("ck_laboratory_availability_type","resource_availability_slots","availability_type IN ('BLOCKED','ALLOWED')")
    op.drop_column("resource_availability_slots","resource_type")
    op.alter_column("resource_availability_slots","resource_id",new_column_name="laboratory_id")
    op.create_foreign_key("fk_laboratory_availability_laboratory","resource_availability_slots","laboratories",["laboratory_id"],["id"])
    op.rename_table("resource_availability_slots","laboratory_availability_blocks")
    op.create_index("uq_laboratory_active_availability_slot","laboratory_availability_blocks",["laboratory_id","academic_term_id","working_day_id","period_number"],unique=True,postgresql_where=sa.text("is_active"))
    op.drop_table("resource_availability_profiles")
