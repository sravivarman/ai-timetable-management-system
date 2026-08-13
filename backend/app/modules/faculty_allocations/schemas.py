"""Faculty allocation schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TheoryAllocationCreate(BaseModel):
    course_offering_id: UUID
    faculty_id: UUID


class TheoryAllocationUpdate(BaseModel):
    faculty_id: UUID


class TheoryAllocationRead(TheoryAllocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; is_active: bool; created_at: datetime; updated_at: datetime


class LaboratoryAllocationCreate(BaseModel):
    course_offering_id: UUID
    faculty_id: UUID
    role_type: Literal["MAIN", "SUPPORTING"]
    required_with_main_faculty_id: UUID | None = None
    alternative_group_code: str | None = Field(default=None, max_length=100)
    minimum_sessions_per_week: int | None = Field(default=None, ge=1)
    maximum_sessions_per_week: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_range(self):
        if self.minimum_sessions_per_week is not None and self.maximum_sessions_per_week is not None and self.maximum_sessions_per_week < self.minimum_sessions_per_week:
            raise ValueError("maximum_sessions_per_week must be at least minimum_sessions_per_week")
        return self


class LaboratoryAllocationUpdate(BaseModel):
    role_type: Literal["MAIN", "SUPPORTING"] | None = None
    required_with_main_faculty_id: UUID | None = None
    alternative_group_code: str | None = Field(default=None, max_length=100)
    minimum_sessions_per_week: int | None = Field(default=None, ge=1)
    maximum_sessions_per_week: int | None = Field(default=None, ge=1)


class LaboratoryAllocationRead(LaboratoryAllocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; is_active: bool; created_at: datetime; updated_at: datetime


class LaboratorySessionRuleCreate(BaseModel):
    laboratory_faculty_allocation_id: UUID
    session_number: int = Field(ge=1)
    is_mandatory_for_session: bool = False


class LaboratorySessionRuleUpdate(BaseModel):
    session_number: int | None = Field(default=None, ge=1)
    is_mandatory_for_session: bool | None = None


class LaboratorySessionRuleRead(LaboratorySessionRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; is_active: bool; created_at: datetime; updated_at: datetime


class AllocationPage(BaseModel):
    items: list[TheoryAllocationRead | LaboratoryAllocationRead | LaboratorySessionRuleRead]
    total: int; page: int; page_size: int; pages: int


class WorkloadPreviewItem(BaseModel):
    faculty_id: UUID
    weekly_workload_hours: int
