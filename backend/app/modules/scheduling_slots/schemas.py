from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotBase(BaseModel):
    academic_term_id: UUID
    slot_code: str = Field(min_length=1, max_length=30)
    slot_name: str = Field(min_length=1, max_length=255)
    sequence_number: int = Field(gt=0)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SchedulingSlotCreate(SlotBase):
    pass


class SchedulingSlotUpdate(BaseModel):
    slot_code: str | None = Field(default=None, min_length=1, max_length=30)
    slot_name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_number: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None


class SchedulingSlotResponse(SlotBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    working_date_count: int = 0
    created_at: datetime
    updated_at: datetime


class SchedulingSlotPage(BaseModel):
    items: list[SchedulingSlotResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WorkingDateCreate(BaseModel):
    working_date: date


class WorkingDateBulkRequest(BaseModel):
    working_dates: list[date]
    replace: bool = False


class WorkingDateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scheduling_slot_id: UUID
    working_date: date
    day_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SlotRequirementCreate(BaseModel):
    scheduling_slot_id: UUID
    course_offering_id: UUID
    sessions_required: int = Field(ge=0)


class SlotRequirementUpdate(BaseModel):
    sessions_required: int | None = Field(default=None, ge=0)


class SlotRequirementResponse(SlotRequirementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SlotRequirementPage(BaseModel):
    items: list[SlotRequirementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RequirementBulkCell(BaseModel):
    scheduling_slot_id: UUID
    course_offering_id: UUID
    sessions_required: int | None = Field(default=None, ge=0)
    clear: bool = False
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def clear_or_value(self):
        if self.clear == (self.sessions_required is not None):
            raise ValueError("Provide sessions_required or clear=true, but not both")
        return self


class RequirementBulkRequest(BaseModel):
    cells: list[RequirementBulkCell] = Field(min_length=1)


class RequirementCopyRequest(BaseModel):
    source_slot_id: UUID
    target_slot_id: UUID
    course_offering_ids: list[UUID] | None = None
    overwrite: bool = False


class RequirementCompleteness(BaseModel):
    scheduling_slot_id: UUID
    slot_code: str
    total_active_offerings: int
    configured_positive: int
    configured_zero: int
    missing: int
    invalid: int = 0
    is_complete: bool


class RequirementMatrixCell(BaseModel):
    scheduling_slot_id: UUID
    requirement_id: UUID | None
    sessions_required: int | None
    status: Literal["MISSING", "CONFIGURED_ZERO", "CONFIGURED"]
    updated_at: datetime | None = None


class RequirementMatrixRow(BaseModel):
    course_offering_id: UUID
    section_id: UUID
    course_code: str
    course_name: str
    course_type: str
    section_code: str
    section_name: str
    semester_requirement_id: UUID | None = None
    semester_required: int | None = None
    allocated_to_slots: int
    remaining_to_allocate: int | None = None
    over_allocated: int
    reconciliation_status: Literal["NOT_CONFIGURED", "UNDER_ALLOCATED", "FULLY_ALLOCATED", "OVER_ALLOCATED"]
    cells: list[RequirementMatrixCell]


class RequirementMatrixResponse(BaseModel):
    slots: list[SchedulingSlotResponse]
    rows: list[RequirementMatrixRow]
    completeness: list[RequirementCompleteness]


class SemesterRequirementCreate(BaseModel):
    academic_term_id: UUID
    course_offering_id: UUID
    total_sessions_required: int = Field(ge=0)


class SemesterRequirementUpdate(BaseModel):
    total_sessions_required: int = Field(ge=0)


class SemesterRequirementResponse(SemesterRequirementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SemesterRequirementBulkCell(BaseModel):
    academic_term_id: UUID
    course_offering_id: UUID
    total_sessions_required: int | None = Field(default=None, ge=0)
    clear: bool = False
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def clear_or_value(self):
        if self.clear == (self.total_sessions_required is not None):
            raise ValueError("Provide total_sessions_required or clear=true, but not both")
        return self


class SemesterRequirementBulkRequest(BaseModel):
    cells: list[SemesterRequirementBulkCell] = Field(min_length=1)


class SemesterRequirementPage(BaseModel):
    items: list[SemesterRequirementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SessionProgressRow(BaseModel):
    academic_year: str
    academic_term: str
    department_code: str
    program_code: str
    section_code: str
    course_code: str
    course_name: str
    course_type: str
    scheduling_slot_id: UUID | None = None
    slot_code: str | None = None
    semester_required: int | None = None
    allocated_to_slots: int
    scheduled_sessions: int
    approved_sessions: int
    published_sessions: int
    remaining_to_allocate: int | None = None
    remaining_to_schedule: int
    remaining_to_publish: int
    reconciliation_status: str
    progress_status: str
