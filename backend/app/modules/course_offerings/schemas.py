"""Course offering request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseOfferingCreate(BaseModel):
    course_id: UUID
    section_id: UUID
    academic_term_id: UUID
    weekly_periods_override: int | None = Field(default=None, gt=0)
    is_mandatory: bool = True
    elective_group_name: str | None = Field(default=None, max_length=255)
    common_theory_group_code: str | None = Field(default=None, max_length=100, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    is_common_theory: bool = Field(default=False, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    laboratory_selection_mode: Literal["AUTO", "PREFERRED", "FIXED"] = "AUTO"
    laboratory_override_id: UUID | None = None

    @field_validator("elective_group_name", "common_theory_group_code")
    @classmethod
    def strip_values(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class CourseOfferingUpdate(BaseModel):
    weekly_periods_override: int | None = Field(default=None, gt=0)
    is_mandatory: bool | None = None
    elective_group_name: str | None = Field(default=None, max_length=255)
    common_theory_group_code: str | None = Field(default=None, max_length=100, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    is_common_theory: bool | None = Field(default=None, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    laboratory_selection_mode: Literal["AUTO", "PREFERRED", "FIXED"] | None = None
    laboratory_override_id: UUID | None = None

    @field_validator("elective_group_name", "common_theory_group_code")
    @classmethod
    def strip_values(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class CourseOfferingRead(CourseOfferingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CourseOfferingPage(BaseModel):
    items: list[CourseOfferingRead]
    total: int
    page: int
    page_size: int
    pages: int


class CourseOfferingBulkCreate(BaseModel):
    academic_term_id: UUID
    section_id: UUID
    course_ids: list[UUID] = Field(min_length=1)
    is_mandatory: bool = True
    elective_group_name: str | None = Field(default=None, max_length=255)
    common_theory_group_code: str | None = Field(default=None, max_length=100, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    is_common_theory: bool = Field(default=False, deprecated=True, description="Deprecated compatibility field. Use Combined Teaching Groups.")
    laboratory_selection_mode: Literal["AUTO", "PREFERRED", "FIXED"] = "AUTO"
    laboratory_override_id: UUID | None = None

    @field_validator("elective_group_name", "common_theory_group_code")
    @classmethod
    def strip_values(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None
