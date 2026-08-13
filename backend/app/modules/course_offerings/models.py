"""Course offering ORM model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint("course_id", "section_id", "academic_term_id", name="uq_course_offering_course_section_term"),
        CheckConstraint(
            "(laboratory_selection_mode = 'AUTO' AND laboratory_override_id IS NULL) OR "
            "(laboratory_selection_mode IN ('PREFERRED', 'FIXED') AND laboratory_override_id IS NOT NULL) OR "
            "(laboratory_selection_mode = 'RESTRICTED' AND laboratory_override_id IS NULL)",
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
    allowed_laboratory_links: Mapped[list["CourseOfferingAllowedLaboratory"]] = relationship(
        back_populates="course_offering", lazy="selectin"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def allowed_laboratory_ids(self) -> list[UUID]:
        return [
            link.laboratory_id
            for link in sorted(
                (item for item in self.allowed_laboratory_links if item.is_active),
                key=lambda item: (item.preference_priority, str(item.laboratory_id)),
            )
        ]


class CourseOfferingAllowedLaboratory(Base):
    """Offering-specific hard subset of the course's capable laboratories."""

    __tablename__ = "course_offering_allowed_laboratories"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "laboratory_id", name="uq_course_offering_allowed_laboratory"),
        CheckConstraint("preference_priority >= 1", name="ck_course_offering_allowed_laboratory_priority"),
    )

    course_offering_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True
    )
    laboratory_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), primary_key=True
    )
    preference_priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    course_offering: Mapped[CourseOffering] = relationship(back_populates="allowed_laboratory_links")
