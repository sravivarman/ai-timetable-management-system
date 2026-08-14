"""Typed report configuration, metadata, and canonical preview schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


OPTIONAL_ENTITY_FILTER_KEYS = frozenset({
    "academic_term_id", "department_id", "program_id", "section_id",
    "course_id", "faculty_id", "faculty_department_id",
})


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

    @model_validator(mode="before")
    @classmethod
    def normalize_optional_filters(cls, value):
        if not isinstance(value, dict) or not isinstance(value.get("filters", {}), dict):
            return value
        normalized = dict(value)
        filters = {}
        for key, raw in value.get("filters", {}).items():
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            if key in OPTIONAL_ENTITY_FILTER_KEYS and isinstance(raw, str) and raw.strip().upper() == "ALL":
                continue
            if isinstance(raw, list):
                items = [item for item in raw if item is not None and (not isinstance(item, str) or item.strip())]
                if key in OPTIONAL_ENTITY_FILTER_KEYS:
                    items = [item for item in items if not isinstance(item, str) or item.strip().upper() != "ALL"]
                if not items:
                    continue
                raw = items
            filters[key] = raw.strip() if isinstance(raw, str) else raw
        normalized["filters"] = filters
        return normalized

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
