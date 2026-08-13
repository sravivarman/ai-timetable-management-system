from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class BatchCreate(BaseModel):
    section_id: UUID
    batch_name: str = Field(min_length=1, max_length=20)
    sequence_number: int = Field(ge=1)
    roll_number_start: int = Field(ge=1)
    roll_number_end: int = Field(ge=1)
    student_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self):
        if self.roll_number_start > self.roll_number_end:
            raise ValueError("roll_number_start must not exceed roll_number_end")
        if self.student_count != self.roll_number_end - self.roll_number_start + 1:
            raise ValueError("student_count must match the roll-number range")
        return self


class BatchUpdate(BatchCreate):
    pass


class BatchRead(BatchCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BatchGenerate(BaseModel):
    section_id: UUID
    number_of_groups: int = Field(ge=1, validation_alias=AliasChoices("number_of_groups", "number_of_batches"))
    overwrite: bool = False
    naming_pattern: str = Field(default="{section}{sequence}", min_length=1, max_length=100)


class ConfigCreate(BaseModel):
    course_offering_id: UUID
    section_id: UUID
    number_of_groups: int = Field(ge=1, validation_alias=AliasChoices("number_of_groups", "number_of_batches"))
    group_naming_pattern: str = Field(default="{section}{sequence}", min_length=1, max_length=100)
    is_rotation_enabled: bool = False
    is_weekly_rotation: bool = False


class ConfigUpdate(BaseModel):
    number_of_groups: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("number_of_groups", "number_of_batches"))
    group_naming_pattern: str | None = Field(default=None, min_length=1, max_length=100)
    is_rotation_enabled: bool | None = None
    is_weekly_rotation: bool | None = None


class ConfigRead(ConfigCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RotationCreate(BaseModel):
    # Legacy clients may still supply one configuration as an anchor.
    laboratory_batch_configuration_id: UUID | None = None
    section_id: UUID | None = None
    academic_term_id: UUID | None = None
    rotation_code: str = Field(min_length=1, max_length=100)
    rotation_type: Literal["FIXED", "CYCLIC"] = "CYCLIC"


class RotationUpdate(BaseModel):
    rotation_code: str | None = Field(default=None, min_length=1, max_length=100)
    rotation_type: Literal["FIXED", "CYCLIC"] | None = None


class RotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    laboratory_batch_configuration_id: UUID | None
    section_id: UUID
    academic_term_id: UUID
    rotation_code: str
    rotation_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RotationBlockCreate(BaseModel):
    block_number: int = Field(ge=1)
    block_name: str | None = Field(default=None, max_length=100)


class RotationBlockUpdate(BaseModel):
    block_number: int | None = Field(default=None, ge=1)
    block_name: str | None = Field(default=None, max_length=100)


class RotationBlockRead(RotationBlockCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rotation_group_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssignmentCreate(BaseModel):
    rotation_block_id: UUID
    batch_id: UUID
    course_offering_id: UUID
    laboratory_id: UUID | None = None
    main_faculty_id: UUID
    supporting_faculty_ids: list[UUID] = Field(default_factory=list)
    session_duration: Literal[2, 3]
    rotation_position: int = Field(ge=1)


class AssignmentUpdate(BaseModel):
    rotation_block_id: UUID | None = None
    batch_id: UUID | None = None
    course_offering_id: UUID | None = None
    laboratory_id: UUID | None = None
    main_faculty_id: UUID | None = None
    supporting_faculty_ids: list[UUID] | None = None
    session_duration: Literal[2, 3] | None = None
    rotation_position: int | None = Field(default=None, ge=1)


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rotation_group_id: UUID
    rotation_block_id: UUID
    batch_id: UUID
    course_offering_id: UUID
    laboratory_id: UUID | None
    main_faculty_id: UUID | None
    supporting_faculty_ids: list[UUID]
    session_duration: int | None
    rotation_position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RotationGenerateRequest(BaseModel):
    section_id: UUID
    academic_term_id: UUID
    rotation_code: str = Field(min_length=1, max_length=100)
    course_offering_ids: list[UUID] = Field(min_length=2)
    student_group_ids: list[UUID] | None = None
    overwrite: bool = False


class RotationBlockDetail(RotationBlockRead):
    assignments: list[AssignmentRead]


class RotationMatrixResponse(BaseModel):
    group: RotationRead
    blocks: list[RotationBlockDetail]
    student_group_ids: list[UUID]
    course_offering_ids: list[UUID]


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
