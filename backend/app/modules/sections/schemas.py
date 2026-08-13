"""Section request and response schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SectionInput(BaseModel):
    section_name: str = Field(min_length=1, max_length=20)
    student_strength: int = Field(gt=0)
    primary_classroom_id: UUID | None = None

    @field_validator("section_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Section name is required")
        return value


class SectionCreate(SectionInput):
    program_id: UUID
    academic_term_id: UUID


class SectionUpdate(BaseModel):
    program_id: UUID | None = None
    academic_term_id: UUID | None = None
    section_name: str | None = Field(default=None, min_length=1, max_length=20)
    student_strength: int | None = Field(default=None, gt=0)
    primary_classroom_id: UUID | None = None

    @field_validator("section_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class SectionRead(SectionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    section_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SectionBulkCreate(BaseModel):
    program_id: UUID
    academic_term_id: UUID
    sections: list[SectionInput] = Field(min_length=1, max_length=50)


class SectionPage(BaseModel):
    items: list[SectionRead]
    total: int
    page: int
    page_size: int
    pages: int
