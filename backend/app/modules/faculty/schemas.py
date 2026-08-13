"""Faculty schemas."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
Designation = Literal["Assistant Professor", "Associate Professor", "Professor"]

class FacultyBase(BaseModel):
    faculty_code: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=255)
    department_id: UUID
    designation: Designation
    institutional_email: EmailStr
    phone_number: str | None = Field(default=None, max_length=30)
    user_id: UUID | None = None
    minimum_weekly_workload: int = Field(default=0, ge=0)
    maximum_weekly_workload: int = Field(ge=0)
    maximum_periods_per_day: int | None = Field(default=None, ge=1, le=7)
    @field_validator("faculty_code")
    @classmethod
    def code(cls, value: str) -> str: return value.strip().upper()
    @model_validator(mode="after")
    def workload(self):
        if self.maximum_weekly_workload < self.minimum_weekly_workload: raise ValueError("maximum_weekly_workload must be at least minimum_weekly_workload")
        return self
class FacultyCreate(FacultyBase): pass
class FacultyUpdate(BaseModel):
    faculty_code: str | None = Field(default=None, min_length=2, max_length=30); full_name: str | None = Field(default=None, min_length=2, max_length=255); department_id: UUID | None = None; designation: Designation | None = None; institutional_email: EmailStr | None = None; phone_number: str | None = None; user_id: UUID | None = None; minimum_weekly_workload: int | None = Field(default=None, ge=0); maximum_weekly_workload: int | None = Field(default=None, ge=0); maximum_periods_per_day: int | None = Field(default=None, ge=1, le=7)
    @field_validator("faculty_code")
    @classmethod
    def code(cls, value: str | None) -> str | None: return value.strip().upper() if value else value
class FacultyRead(FacultyBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; is_active: bool; created_at: datetime; updated_at: datetime
class FacultyPage(BaseModel):
    items: list[FacultyRead]; total: int; page: int; page_size: int; pages: int
