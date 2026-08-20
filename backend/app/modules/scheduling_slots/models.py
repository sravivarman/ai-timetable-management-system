from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class SchedulingSlot(Base):
    __tablename__ = "scheduling_slots"
    __table_args__ = (
        UniqueConstraint("academic_term_id", "slot_code", name="uq_scheduling_slot_term_code"),
        UniqueConstraint("academic_term_id", "sequence_number", name="uq_scheduling_slot_term_sequence"),
        CheckConstraint("sequence_number > 0", name="ck_scheduling_slot_positive_sequence"),
        CheckConstraint("end_date >= start_date", name="ck_scheduling_slot_date_range"),
        Index("ix_scheduling_slots_term_active", "academic_term_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False)
    slot_code: Mapped[str] = mapped_column(String(30), nullable=False)
    slot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SchedulingSlotWorkingDate(Base):
    __tablename__ = "scheduling_slot_working_dates"
    __table_args__ = (
        UniqueConstraint("scheduling_slot_id", "working_date", name="uq_scheduling_slot_working_date"),
        Index("ix_scheduling_slot_working_dates_active_date", "working_date", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    scheduling_slot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("scheduling_slots.id", ondelete="RESTRICT"), nullable=False, index=True)
    working_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SlotCourseRequirement(Base):
    __tablename__ = "slot_course_requirements"
    __table_args__ = (
        UniqueConstraint("scheduling_slot_id", "course_offering_id", name="uq_slot_course_requirement"),
        CheckConstraint("sessions_required >= 0", name="ck_slot_requirement_non_negative"),
        Index("ix_slot_requirements_slot_active", "scheduling_slot_id", "is_active"),
        Index("ix_slot_requirements_offering_active", "course_offering_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    scheduling_slot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("scheduling_slots.id", ondelete="RESTRICT"), nullable=False)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False)
    sessions_required: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CourseOfferingSemesterRequirement(Base):
    __tablename__ = "course_offering_semester_requirements"
    __table_args__ = (
        UniqueConstraint("course_offering_id", name="uq_semester_requirement_offering"),
        CheckConstraint("total_sessions_required >= 0", name="ck_semester_requirement_non_negative"),
        Index("ix_semester_requirements_term_active", "academic_term_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    total_sessions_required: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
