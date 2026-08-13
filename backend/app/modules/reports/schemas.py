"""Typed report configuration, metadata, and canonical preview schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ColumnMetadata(BaseModel):
    key: str
    label: str
    group: str
    data_type: str
    sortable: bool
    default_width: int
    alignment: str


class FilterMetadata(BaseModel):
    key: str
    label: str
    control: str
    options: list[str] = Field(default_factory=list)


class SortField(BaseModel):
    key: str
    direction: Literal["asc", "desc"] = "asc"


class ReportDefinitionResponse(BaseModel):
    key: str
    title: str
    description: str
    layout_type: str
    columns: list[ColumnMetadata]
    default_columns: list[str]
    filters: list[FilterMetadata]
    default_sort: list[SortField]
    supported_formats: list[str]


class ReportRequest(BaseModel):
    report_key: str
    filters: dict[str, Any] = Field(default_factory=dict)
    selected_columns: list[str]
    sort_fields: list[SortField] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @field_validator("selected_columns")
    @classmethod
    def columns_are_nonempty_and_unique(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Select at least one report column")
        if len(value) != len(set(value)):
            raise ValueError("Duplicate report columns are not allowed")
        return value


class ReportPreviewResponse(BaseModel):
    report_key: str
    title: str
    columns: list[ColumnMetadata]
    filters: dict[str, Any]
    filter_summary: list[str]
    sorting: list[SortField]
    rows: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    pages: int
    configuration_signature: str
