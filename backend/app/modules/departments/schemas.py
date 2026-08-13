"""Department request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DepartmentBase(BaseModel):
    department_code: str = Field(min_length=2, max_length=20)
    department_name: str = Field(min_length=2, max_length=255)
    short_name: str = Field(min_length=2, max_length=100)

    @field_validator("department_code")
    @classmethod
    def normalize_department_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Department code is required")
        return normalized

    @field_validator("department_name", "short_name")
    @classmethod
    def trim_required_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field is required")
        return normalized


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    department_code: str | None = Field(default=None, min_length=2, max_length=20)
    department_name: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("department_code")
    @classmethod
    def normalize_department_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Department code is required")
        return normalized

    @field_validator("department_name", "short_name")
    @classmethod
    def trim_optional_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field is required")
        return normalized


class DepartmentRead(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentPage(BaseModel):
    items: list[DepartmentRead]
    total: int
    page: int
    page_size: int
    pages: int
