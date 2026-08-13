"""Section ORM entity."""

from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.db.base import Base


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("program_id", "academic_term_id", "section_name", name="uq_sections_program_term_name"),
        UniqueConstraint("program_id", "academic_term_id", "section_code", name="uq_sections_program_term_code"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), index=True, nullable=False)
    academic_term_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), index=True, nullable=False)
    section_name: Mapped[str] = mapped_column(String(20), nullable=False)
    section_code: Mapped[str] = mapped_column(String(60), nullable=False)
    student_strength: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_classroom_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
