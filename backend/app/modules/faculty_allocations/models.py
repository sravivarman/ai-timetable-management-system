"""Faculty allocation ORM entities."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class TheoryFacultyAllocation(Base):
    __tablename__ = "theory_faculty_allocations"
    __table_args__ = (UniqueConstraint("course_offering_id", "faculty_id", name="uq_theory_allocation_offering_faculty"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    faculty_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LaboratoryFacultyAllocation(Base):
    __tablename__ = "laboratory_faculty_allocations"
    __table_args__ = (UniqueConstraint("course_offering_id", "faculty_id", "role_type", name="uq_laboratory_allocation_offering_faculty_role"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_offering_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    faculty_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False, index=True)
    role_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    required_with_main_faculty_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"))
    alternative_group_code: Mapped[str | None] = mapped_column(String(100))
    minimum_sessions_per_week: Mapped[int | None] = mapped_column(Integer)
    maximum_sessions_per_week: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LaboratorySessionFacultyRule(Base):
    __tablename__ = "laboratory_session_faculty_rules"
    __table_args__ = (UniqueConstraint("laboratory_faculty_allocation_id", "session_number", name="uq_lab_session_faculty_rule"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    laboratory_faculty_allocation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratory_faculty_allocations.id", ondelete="RESTRICT"), nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mandatory_for_session: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
