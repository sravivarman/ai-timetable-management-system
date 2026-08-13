"""Academic term request and response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TERM_NAMES = {(1, 1): "I-I", (1, 2): "I-II", (2, 1): "II-I", (2, 2): "II-II", (3, 1): "III-I", (3, 2): "III-II", (4, 1): "IV-I", (4, 2): "IV-II"}


class AcademicTermBase(BaseModel):
    academic_year: str = Field(min_length=7, max_length=9, pattern=r"^\d{4}-\d{2}$")
    term_name: str = Field(min_length=3, max_length=10)
    year_number: int = Field(ge=1, le=4)
    semester_number: int = Field(ge=1, le=2)
    start_date: date
    end_date: date
    is_active: bool = False
    is_current: bool = False
    is_first_year_term: bool = False

    @field_validator("academic_year", "term_name")
    @classmethod
    def trim_values(cls, value: str) -> str:
        return value.strip().upper() if value.strip() else value

    @model_validator(mode="after")
    def validate_term(self):
        expected_term = TERM_NAMES[(self.year_number, self.semester_number)]
        if self.term_name != expected_term:
            raise ValueError(f"term_name must be {expected_term} for the selected year and semester")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.is_current and not self.is_active:
            raise ValueError("A current term must be active")
        return self


class AcademicTermCreate(AcademicTermBase):
    pass


class AcademicTermUpdate(BaseModel):
    academic_year: str | None = Field(default=None, min_length=7, max_length=9, pattern=r"^\d{4}-\d{2}$")
    term_name: str | None = Field(default=None, min_length=3, max_length=10)
    year_number: int | None = Field(default=None, ge=1, le=4)
    semester_number: int | None = Field(default=None, ge=1, le=2)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    is_current: bool | None = None
    is_first_year_term: bool | None = None

    @field_validator("academic_year", "term_name")
    @classmethod
    def trim_optional_values(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class AcademicTermRead(AcademicTermBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class AcademicTermPage(BaseModel):
    items: list[AcademicTermRead]
    total: int
    page: int
    page_size: int
    pages: int
