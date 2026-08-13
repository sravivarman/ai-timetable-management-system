from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class StudentBatch(Base):
    __tablename__ = "student_batches"
    __table_args__ = (
        Index("uq_active_batch_section_name", "section_id", "batch_name", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active")),
        Index("uq_active_batch_section_sequence", "section_id", "sequence_number", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sections.id", ondelete="RESTRICT"), index=True)
    batch_name: Mapped[str] = mapped_column(String(20))
    sequence_number: Mapped[int] = mapped_column(Integer)
    roll_number_start: Mapped[int] = mapped_column(Integer)
    roll_number_end: Mapped[int] = mapped_column(Integer)
    student_count: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LaboratoryBatchConfiguration(Base):
    __tablename__ = "laboratory_batch_configurations"
    __table_args__ = (
        UniqueConstraint("course_offering_id", name="uq_lab_batch_configuration_offering"),
        CheckConstraint("number_of_groups >= 1", name="ck_laboratory_batch_configurations_group_count_positive"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), index=True)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sections.id", ondelete="RESTRICT"), index=True)
    number_of_groups: Mapped[int] = mapped_column(Integer)
    group_naming_pattern: Mapped[str] = mapped_column(String(100), default="{section}{sequence}")
    is_rotation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_weekly_rotation: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LaboratoryRotationGroup(Base):
    __tablename__ = "laboratory_rotation_groups"
    __table_args__ = (
        Index("uq_active_rotation_group_code", "section_id", "academic_term_id", "rotation_code", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # Retained as an optional legacy anchor. New groups are section/term scoped.
    laboratory_batch_configuration_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratory_batch_configurations.id", ondelete="RESTRICT"), index=True)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sections.id", ondelete="RESTRICT"), index=True)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), index=True)
    rotation_code: Mapped[str] = mapped_column(String(100))
    rotation_type: Mapped[str] = mapped_column(String(20), default="CYCLIC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LaboratoryRotationBlock(Base):
    __tablename__ = "laboratory_rotation_blocks"
    __table_args__ = (
        UniqueConstraint("rotation_group_id", "block_number", name="uq_rotation_block_number"),
        CheckConstraint("block_number >= 1", name="ck_rotation_block_number_positive"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rotation_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratory_rotation_groups.id", ondelete="CASCADE"), index=True)
    block_number: Mapped[int] = mapped_column(Integer)
    block_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LaboratoryRotationAssignment(Base):
    __tablename__ = "laboratory_rotation_assignments"
    __table_args__ = (
        UniqueConstraint("rotation_block_id", "batch_id", name="uq_rotation_block_student_group"),
        UniqueConstraint("rotation_block_id", "course_offering_id", name="uq_rotation_block_offering"),
        UniqueConstraint("rotation_block_id", "rotation_position", name="uq_rotation_block_position"),
        CheckConstraint("rotation_position >= 1", name="ck_rotation_assignment_position_positive"),
        CheckConstraint("session_duration IS NULL OR session_duration IN (2, 3)", name="ck_rotation_assignment_session_duration"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rotation_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratory_rotation_groups.id", ondelete="CASCADE"), index=True)
    rotation_block_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratory_rotation_blocks.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("student_batches.id", ondelete="RESTRICT"), index=True)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), index=True)
    laboratory_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True)
    main_faculty_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), index=True)
    supporting_faculty_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    session_duration: Mapped[int | None] = mapped_column(Integer)
    rotation_position: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
