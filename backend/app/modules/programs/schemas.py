"""Program request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProgramBase(BaseModel):
    department_id: UUID
    program_code: str = Field(min_length=2, max_length=30)
    program_name: str = Field(min_length=2, max_length=255)
    degree_type: Literal["UG"] = "UG"
    duration_years: int = Field(default=4, ge=4, le=4)

    @field_validator("program_code")
    @classmethod
    def normalize_program_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Program code is required")
        return normalized

    @field_validator("program_name")
    @classmethod
    def trim_program_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Program name is required")
        return normalized


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    department_id: UUID | None = None
    program_code: str | None = Field(default=None, min_length=2, max_length=30)
    program_name: str | None = Field(default=None, min_length=2, max_length=255)
    degree_type: Literal["UG"] | None = None
    duration_years: int | None = Field(default=None, ge=4, le=4)

    @field_validator("program_code")
    @classmethod
    def normalize_program_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Program code is required")
        return normalized

    @field_validator("program_name")
    @classmethod
    def trim_program_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Program name is required")
        return normalized


class ProgramRead(ProgramBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProgramPage(BaseModel):
    items: list[ProgramRead]
    total: int
    page: int
    page_size: int
    pages: int
