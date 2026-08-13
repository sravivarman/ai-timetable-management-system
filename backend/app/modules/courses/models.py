"""Course master ORM model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base

def _grouping_default(context) -> str:
    return "GROUPED" if (context.get_current_parameters().get("default_lab_group_count") or 1) > 1 else "FULL_SECTION"

def _venue_default(context) -> str:
    course_type = context.get_current_parameters().get("course_type")
    return "LABORATORY_ONLY" if course_type == "LABORATORY" else "CLASSROOM_ONLY" if course_type in {"THEORY", "CDC"} else "NO_FIXED_VENUE"

def _duration_default(context) -> int:
    return context.get_current_parameters().get("lab_session_duration") or 1

def _sessions_default(context) -> int:
    values = context.get_current_parameters()
    return values.get("lab_sessions_per_week") or values.get("weekly_periods") or 1

def _group_count_default(context) -> int:
    return context.get_current_parameters().get("default_lab_group_count") or 1


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "default_lab_group_count IS NULL OR default_lab_group_count >= 1",
            name="ck_courses_default_lab_group_count_positive",
        ),
        CheckConstraint("session_duration >= 1", name="ck_courses_session_duration_positive"),
        CheckConstraint("sessions_per_week >= 1", name="ck_courses_sessions_per_week_positive"),
        CheckConstraint("default_group_count >= 1", name="ck_courses_default_group_count_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offering_department_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), index=True, nullable=False)
    course_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    grouping_mode: Mapped[str] = mapped_column(String(20), default=_grouping_default, nullable=False)
    venue_requirement: Mapped[str] = mapped_column(String(40), default=_venue_default, nullable=False)
    elective_type: Mapped[str | None] = mapped_column(String(30), index=True)
    weekly_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    allows_same_course_double_period: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    session_duration: Mapped[int] = mapped_column(Integer, default=_duration_default, nullable=False)
    sessions_per_week: Mapped[int] = mapped_column(Integer, default=_sessions_default, nullable=False)
    default_group_count: Mapped[int] = mapped_column(Integer, default=_group_count_default, nullable=False)
    # Historical compatibility fields. Generic scheduling uses the three fields
    # above; these remain populated for existing laboratory clients/rotations.
    lab_session_duration: Mapped[int | None] = mapped_column(Integer)
    lab_sessions_per_week: Mapped[int | None] = mapped_column(Integer)
    default_lab_group_count: Mapped[int | None] = mapped_column(Integer)
    default_laboratory_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"))
    counts_toward_workload: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    eligible_laboratory_links: Mapped[list["CourseEligibleLaboratory"]] = relationship(
        back_populates="course", lazy="selectin"
    )

    @property
    def eligible_laboratory_ids(self) -> list[UUID]:
        return [
            link.laboratory_id
            for link in sorted(
                (item for item in self.eligible_laboratory_links if item.is_active),
                key=lambda item: (item.preference_priority, str(item.laboratory_id)),
            )
        ]


class CourseEligibleLaboratory(Base):
    """Explicit technical suitability between a course and a physical laboratory."""

    __tablename__ = "course_eligible_laboratories"
    __table_args__ = (
        UniqueConstraint("course_id", "laboratory_id", name="uq_course_eligible_laboratory"),
        CheckConstraint("preference_priority >= 1", name="ck_course_eligible_laboratory_priority"),
    )

    course_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    laboratory_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("laboratories.id", ondelete="RESTRICT"), primary_key=True
    )
    preference_priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    course: Mapped[Course] = relationship(back_populates="eligible_laboratory_links")
