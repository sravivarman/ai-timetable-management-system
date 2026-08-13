"""Course master request and response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

CourseType = Literal["THEORY", "LABORATORY", "PRACTICAL", "CDC", "LSM", "MINI_PROJECT", "PROJECT"]
ElectiveType = Literal["PROFESSIONAL_ELECTIVE", "OPEN_ELECTIVE"]
GroupingMode = Literal["FULL_SECTION", "GROUPED"]
VenueRequirement = Literal["CLASSROOM_ONLY", "LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY", "NO_FIXED_VENUE"]


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=255)
    offering_department_id: UUID
    course_type: CourseType
    grouping_mode: GroupingMode | None = None
    venue_requirement: VenueRequirement | None = None
    elective_type: ElectiveType | None = None
    weekly_periods: int = Field(gt=0)
    credits: Decimal | None = Field(default=None, ge=0)
    allows_same_course_double_period: bool = False
    session_duration: int | None = Field(default=None, ge=1, le=3)
    sessions_per_week: int | None = Field(default=None, ge=1)
    default_group_count: int | None = Field(default=None, ge=1)
    lab_session_duration: Literal[2, 3] | None = None
    lab_sessions_per_week: int | None = Field(default=None, ge=1)
    default_lab_group_count: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("default_lab_group_count", "lab_batch_count"))
    default_laboratory_id: UUID | None = None
    eligible_laboratory_ids: list[UUID] = Field(default_factory=list)
    counts_toward_workload: bool | None = None

    @field_validator("course_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Course code is required")
        return value

    @field_validator("course_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Course name is required")
        return value

    @field_validator("eligible_laboratory_ids")
    @classmethod
    def unique_eligible_laboratories(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Eligible laboratories must be unique")
        return value


class CourseUpdate(BaseModel):
    course_code: str | None = Field(default=None, min_length=1, max_length=50)
    course_name: str | None = Field(default=None, min_length=1, max_length=255)
    offering_department_id: UUID | None = None
    course_type: CourseType | None = None
    grouping_mode: GroupingMode | None = None
    venue_requirement: VenueRequirement | None = None
    elective_type: ElectiveType | None = None
    weekly_periods: int | None = Field(default=None, gt=0)
    credits: Decimal | None = Field(default=None, ge=0)
    allows_same_course_double_period: bool | None = None
    session_duration: int | None = Field(default=None, ge=1, le=3)
    sessions_per_week: int | None = Field(default=None, ge=1)
    default_group_count: int | None = Field(default=None, ge=1)
    lab_session_duration: Literal[2, 3] | None = None
    lab_sessions_per_week: int | None = Field(default=None, ge=1)
    default_lab_group_count: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("default_lab_group_count", "lab_batch_count"))
    default_laboratory_id: UUID | None = None
    eligible_laboratory_ids: list[UUID] | None = None
    counts_toward_workload: bool | None = None

    @field_validator("course_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else value

    @field_validator("course_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class CourseRead(CourseCreate):
    model_config = ConfigDict(from_attributes=True)
    counts_toward_workload: bool
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime



class CoursePage(BaseModel):
    items: list[CourseRead]
    total: int
    page: int
    page_size: int
    pages: int
