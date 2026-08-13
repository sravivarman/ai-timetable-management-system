from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
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
