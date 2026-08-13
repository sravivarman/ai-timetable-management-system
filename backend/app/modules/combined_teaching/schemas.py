"""API contracts for combined teaching configuration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CombinedTeachingGroupCreate(BaseModel):
    academic_term_id: UUID
    group_code: str = Field(min_length=1, max_length=80)
    group_name: str = Field(min_length=1, max_length=255)
    course_id: UUID
    faculty_id: UUID
    preferred_classroom_id: UUID | None = None
    preferred_laboratory_id: UUID | None = None
    course_offering_ids: list[UUID] = Field(min_length=2)
    is_active: bool = True

    @field_validator("group_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CombinedTeachingGroupUpdate(BaseModel):
    academic_term_id: UUID | None = None
    group_code: str | None = Field(default=None, min_length=1, max_length=80)
    group_name: str | None = Field(default=None, min_length=1, max_length=255)
    course_id: UUID | None = None
    faculty_id: UUID | None = None
    preferred_classroom_id: UUID | None = None
    preferred_laboratory_id: UUID | None = None
    course_offering_ids: list[UUID] | None = Field(default=None, min_length=2)

    @field_validator("group_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CombinedOfferingResponse(BaseModel):
    course_offering_id: UUID
    section_id: UUID
    section_code: str
    section_strength: int
    course_code: str
    course_name: str
    model_config = ConfigDict(from_attributes=True)


class CombinedTeachingGroupResponse(BaseModel):
    id: UUID
    academic_term_id: UUID
    group_code: str
    group_name: str
    course_id: UUID
    faculty_id: UUID
    preferred_classroom_id: UUID | None
    preferred_laboratory_id: UUID | None
    is_active: bool
    combined_strength: int
    venue_capacity: int | None
    capacity_status: str
    offerings: list[CombinedOfferingResponse]
    created_at: datetime
    updated_at: datetime


class CombinedTeachingGroupPage(BaseModel):
    items: list[CombinedTeachingGroupResponse]
    total: int
    page: int
    page_size: int
    pages: int
