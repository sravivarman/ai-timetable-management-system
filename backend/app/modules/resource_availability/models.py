from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, synonym
from sqlalchemy.types import Uuid

from app.db.base import Base


class ResourceAvailabilityProfile(Base):
    __tablename__ = "resource_availability_profiles"
    __table_args__ = (
        Index("uq_active_resource_availability_profile", "resource_type", "resource_id", "academic_term_id", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active = 1")),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), index=True)
    availability_mode: Mapped[str] = mapped_column(String(24), default="ALL_PERIODS", server_default="ALL_PERIODS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResourceAvailabilitySlot(Base):
    __tablename__ = "resource_availability_slots"
    __table_args__ = (
        Index("uq_active_resource_availability_slot", "resource_type", "resource_id", "academic_term_id", "working_day_id", "period_number", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active = 1")),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(40), default="LABORATORY", server_default="LABORATORY", index=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    laboratory_id = synonym("resource_id")  # legacy API/ORM compatibility
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), index=True)
    working_day_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("working_days.id", ondelete="RESTRICT"), index=True)
    period_number: Mapped[int] = mapped_column(Integer)
    availability_type: Mapped[str] = mapped_column(String(12), default="BLOCKED", server_default="BLOCKED")
    reason: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


LaboratoryAvailabilityBlock = ResourceAvailabilitySlot


class ResourceDateException(Base):
    """One-off availability override. Null period bounds mean the complete date."""
    __tablename__ = "resource_date_exceptions"
    __table_args__ = (
        CheckConstraint("availability_status IN ('AVAILABLE', 'UNAVAILABLE')", name="ck_resource_date_exception_status"),
        CheckConstraint("(period_start IS NULL AND period_end IS NULL) OR (period_start BETWEEN 1 AND 7 AND period_end BETWEEN period_start AND 7)", name="ck_resource_date_exception_period_range"),
        Index("ix_resource_date_exceptions_lookup", "resource_type", "resource_id", "academic_term_id", "exception_date", "is_active"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True)
    exception_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_start: Mapped[int | None] = mapped_column(Integer)
    period_end: Mapped[int | None] = mapped_column(Integer)
    availability_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
