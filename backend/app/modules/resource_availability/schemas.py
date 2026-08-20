from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AvailabilityMode = Literal["ALL_PERIODS", "EXCEPT_BLOCKED", "ONLY_SELECTED"]
SlotType = Literal["BLOCKED", "ALLOWED"]


class ResourceAvailabilityProfileUpdate(BaseModel):
    availability_mode: AvailabilityMode


class ResourceAvailabilityProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    resource_type: str
    resource_id: UUID
    academic_term_id: UUID
    availability_mode: AvailabilityMode
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ResourceAvailabilitySlotCreate(BaseModel):
    resource_type: str
    resource_id: UUID
    academic_term_id: UUID
    working_day_id: UUID
    period_number: int = Field(ge=1, le=7)
    availability_type: SlotType
    reason: str | None = None


class ResourceAvailabilitySlotUpdate(BaseModel):
    period_number: int | None = Field(default=None, ge=1, le=7)
    availability_type: SlotType | None = None
    reason: str | None = None


class ResourceAvailabilitySlotResponse(ResourceAvailabilitySlotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ResourceDateExceptionCreate(BaseModel):
    resource_type: str
    resource_id: UUID
    academic_term_id: UUID
    exception_date: date
    period_start: int | None = Field(default=None, ge=1, le=7)
    period_end: int | None = Field(default=None, ge=1, le=7)
    availability_status: Literal["AVAILABLE", "UNAVAILABLE"]
    reason: str | None = None


class ResourceDateExceptionResponse(ResourceDateExceptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
