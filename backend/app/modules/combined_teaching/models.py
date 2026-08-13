"""Persistence for common classes shared by two or more section offerings."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class CombinedTeachingGroup(Base):
    __tablename__ = "combined_teaching_groups"
    __table_args__ = (UniqueConstraint("academic_term_id", "group_code", name="uq_combined_teaching_term_code"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True)
    group_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True)
    faculty_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False, index=True)
    preferred_classroom_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True)
    preferred_laboratory_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CombinedTeachingGroupMember(Base):
    __tablename__ = "combined_teaching_group_members"
    __table_args__ = (UniqueConstraint("combined_teaching_group_id", "course_offering_id", name="uq_combined_teaching_group_offering"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    combined_teaching_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("combined_teaching_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CombinedTeachingEvent(Base):
    """One logical resource-consuming event expanded into section child entries."""

    __tablename__ = "combined_teaching_events"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    timetable_version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("timetable_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    combined_teaching_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("combined_teaching_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    working_day_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("working_days.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_length: Mapped[int] = mapped_column(Integer, nullable=False)
    faculty_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False, index=True)
    classroom_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True)
    laboratory_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
