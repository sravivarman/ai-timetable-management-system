"""Course offering ORM model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint("course_id", "section_id", "academic_term_id", name="uq_course_offering_course_section_term"),
        CheckConstraint(
            "(laboratory_selection_mode = 'AUTO' AND laboratory_override_id IS NULL) OR "
            "(laboratory_selection_mode IN ('PREFERRED', 'FIXED') AND laboratory_override_id IS NOT NULL)",
            name="ck_course_offering_laboratory_selection",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False, index=True)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True)
    weekly_periods_override: Mapped[int | None] = mapped_column(Integer)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    elective_group_name: Mapped[str | None] = mapped_column(String(255))
    # Deprecated wire/storage compatibility only. CombinedTeachingGroup is the
    # sole authoritative source for synchronized multi-section teaching.
    common_theory_group_code: Mapped[str | None] = mapped_column(String(100), index=True)
    is_common_theory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    laboratory_selection_mode: Mapped[str] = mapped_column(String(20), default="AUTO", nullable=False, index=True)
    laboratory_override_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
