"""Canonical, read-only report datasets shared by preview and exporters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering, CourseOfferingAllowedLaboratory
from app.modules.courses.models import Course
from app.modules.departments.models import Department
from app.modules.facilities.models import Classroom, Laboratory
from app.modules.facilities_constraints.models import SectionClassroomAssignment
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.eligibility import uses_activity_faculty_allocations
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.faculty_allocations.workload import configured_faculty_workloads
from app.modules.programs.models import Program
from app.modules.reports.columns import COLUMNS, ReportColumn
from app.modules.reports.definitions import REPORTS, ReportDefinition
from app.modules.reports.schemas import (
    ColumnMetadata,
    FilterMetadata,
    ReportDefinitionResponse,
    ReportPreviewResponse,
    ReportRequest,
    SortField,
)
from app.modules.sections.models import Section


ENTITY_FILTERS = {
    "academic_term_id": AcademicTerm,
    "department_id": Department,
    "program_id": Program,
    "section_id": Section,
    "course_id": Course,
    "faculty_id": Faculty,
    "faculty_department_id": Department,
}


@dataclass(frozen=True)
class CanonicalReport:
    definition: ReportDefinition
    columns: tuple[ReportColumn, ...]
    filters: dict[str, Any]
    filter_summary: tuple[str, ...]
    sorting: tuple[SortField, ...]
    rows: tuple[dict[str, Any], ...]
    signature: str


class ReportService:
    """Build validated canonical results without mutating domain data."""

    def definitions(self) -> list[ReportDefinitionResponse]:
        return [self._definition_response(definition) for definition in REPORTS.values()]

    def canonical(self, db: Session, request: ReportRequest) -> CanonicalReport:
        definition = REPORTS.get(request.report_key)
        if definition is None:
            raise HTTPException(404, "Unknown report")
        self._validate_request(db, definition, request)
        provider = getattr(self, f"_provide_{definition.key}")
        rows = provider(db)
        rows = [row for row in rows if self._matches(row, request.filters)]
        sorting = tuple(request.sort_fields or [SortField(key=key, direction=direction) for key, direction in definition.default_sort])
        rows = self._sort(rows, sorting)
        selected = tuple(COLUMNS[key] for key in request.selected_columns)
        visible = tuple({key: self._display(row.get(key), COLUMNS[key]) for key in request.selected_columns} for row in rows)
        signature_payload = {
            "report_key": request.report_key,
            "filters": request.filters,
            "selected_columns": request.selected_columns,
            "sort_fields": [item.model_dump() for item in sorting],
        }
        signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        return CanonicalReport(
            definition=definition,
            columns=selected,
            filters=request.filters,
            filter_summary=tuple(self._filter_summary(db, definition, request.filters)),
            sorting=sorting,
            rows=visible,
            signature=signature,
        )

    def preview(self, db: Session, request: ReportRequest) -> ReportPreviewResponse:
        result = self.canonical(db, request)
        start = (request.page - 1) * request.page_size
        return ReportPreviewResponse(
            report_key=result.definition.key,
            title=result.definition.title,
            columns=[self._column_response(column) for column in result.columns],
            filters=result.filters,
            filter_summary=list(result.filter_summary),
            sorting=list(result.sorting),
            rows=list(result.rows[start : start + request.page_size]),
            total=len(result.rows),
            page=request.page,
            page_size=request.page_size,
            pages=ceil(len(result.rows) / request.page_size) if result.rows else 0,
            configuration_signature=result.signature,
        )

    def _validate_request(self, db: Session, definition: ReportDefinition, request: ReportRequest) -> None:
        unknown_columns = set(request.selected_columns) - set(definition.allowed_columns)
        if unknown_columns:
            raise HTTPException(422, f"Columns are not allowed for this report: {', '.join(sorted(unknown_columns))}")
        allowed_filters = {item.key: item for item in definition.filters}
        unknown_filters = set(request.filters) - set(allowed_filters)
        if unknown_filters:
            raise HTTPException(422, f"Filters are not allowed for this report: {', '.join(sorted(unknown_filters))}")
        for key, raw in request.filters.items():
            values = raw if isinstance(raw, list) else [raw]
            if key in ENTITY_FILTERS:
                for value in values:
                    try:
                        entity_id = UUID(str(value))
                    except ValueError as exc:
                        raise HTTPException(422, f"Invalid {key}") from exc
                    if db.get(ENTITY_FILTERS[key], entity_id) is None:
                        raise HTTPException(422, f"Referenced {allowed_filters[key].label.lower()} does not exist")
            elif allowed_filters[key].options:
                normalized = {str(value).upper() for value in values}
                allowed = set(allowed_filters[key].options)
                if not normalized <= allowed:
                    raise HTTPException(422, f"Invalid {allowed_filters[key].label.lower()}")
        for sort in request.sort_fields:
            if sort.key not in definition.allowed_columns or not COLUMNS[sort.key].sortable:
                raise HTTPException(422, f"Sorting by '{sort.key}' is not allowed for this report")

    @staticmethod
    def _matches(row: dict[str, Any], filters: dict[str, Any]) -> bool:
        status = str(filters.get("status", "ACTIVE")).upper()
        if status != "ALL" and row.get("record_status") != status.title():
            return False
        for key, raw in filters.items():
            if key == "status":
                continue
            values = raw if isinstance(raw, list) else [raw]
            expected = {str(value).upper() for value in values if value not in (None, "", "ALL")}
            if not expected:
                continue
            actual_key = {
                "allocation_status": "faculty_allocation_status",
                "role_type": "faculty_role",
            }.get(key, f"__{key}" if key.endswith("_id") else key)
            actual = row.get(actual_key)
            if str(actual).upper() not in expected:
                return False
        return True

    @staticmethod
    def _sort(rows: list[dict[str, Any]], sorting: tuple[SortField, ...]) -> list[dict[str, Any]]:
        ordered = list(rows)
        ordered.sort(key=lambda row: str(row.get("__stable_id", "")))
        for field in reversed(sorting):
            ordered.sort(
                key=lambda row: (row.get(field.key) is None, str(row.get(field.key) or "").casefold()),
                reverse=field.direction == "desc",
            )
        return ordered

    @staticmethod
    def _display(value: Any, column: ReportColumn) -> Any:
        if value is None:
            return None
        if column.data_type == "boolean":
            return "Yes" if value else "No"
        return value

    def _definition_response(self, definition: ReportDefinition) -> ReportDefinitionResponse:
        return ReportDefinitionResponse(
            key=definition.key,
            title=definition.title,
            description=definition.description,
            layout_type=definition.layout_type,
            columns=[self._column_response(COLUMNS[key]) for key in definition.allowed_columns],
            default_columns=list(definition.default_columns),
            filters=[FilterMetadata(key=item.key, label=item.label, control=item.control, options=list(item.options)) for item in definition.filters],
            default_sort=[SortField(key=key, direction=direction) for key, direction in definition.default_sort],
            supported_formats=list(definition.supported_formats),
        )

    @staticmethod
    def _column_response(column: ReportColumn) -> ColumnMetadata:
        return ColumnMetadata(**column.__dict__)

    def _filter_summary(self, db: Session, definition: ReportDefinition, filters: dict[str, Any]) -> list[str]:
        summaries: list[str] = []
        labels = {item.key: item.label for item in definition.filters}
        for key, raw in filters.items():
            values = raw if isinstance(raw, list) else [raw]
            readable: list[str] = []
            for value in values:
                if key in ENTITY_FILTERS:
                    entity = db.get(ENTITY_FILTERS[key], UUID(str(value)))
                    readable.append(self._entity_label(entity))
                else:
                    readable.append(str(value).replace("_", " ").title())
            summaries.append(f"{labels[key]}: {', '.join(readable)}")
        if not any(item.startswith("Status:") for item in summaries) and any(item.key == "status" for item in definition.filters):
            summaries.append("Status: Active")
        return summaries

    @staticmethod
    def _entity_label(entity: Any) -> str:
        if isinstance(entity, AcademicTerm): return f"{entity.academic_year} • {entity.term_name}"
        if isinstance(entity, Department): return f"{entity.department_code} • {entity.department_name}"
        if isinstance(entity, Program): return f"{entity.program_code} • {entity.program_name}"
        if isinstance(entity, Section): return entity.section_code
        if isinstance(entity, Course): return f"{entity.course_code} • {entity.course_name}"
        if isinstance(entity, Faculty): return f"{entity.faculty_code} • {entity.full_name}"
        return "Unknown"

    def _provide_faculty_master(self, db: Session) -> list[dict[str, Any]]:
        departments = {item.id: item for item in db.scalars(select(Department))}
        rows = []
        for faculty in db.scalars(select(Faculty)):
            department = departments.get(faculty.department_id)
            rows.append({
                "faculty_code": faculty.faculty_code, "faculty_name": faculty.full_name,
                "department_code": department.department_code if department else None,
                "department_name": department.department_name if department else None,
                "designation": faculty.designation, "institutional_email": faculty.institutional_email,
                "phone_number": faculty.phone_number, "minimum_workload": faculty.minimum_weekly_workload,
                "maximum_workload": faculty.maximum_weekly_workload, "record_status": self._status(faculty.is_active),
                "__department_id": faculty.department_id, "__faculty_id": faculty.id,
                "__designation": faculty.designation, "__stable_id": faculty.id,
            })
        return rows

    def _offering_contexts(self, db: Session) -> list[dict[str, Any]]:
        departments = {item.id: item for item in db.scalars(select(Department))}
        programs = {item.id: item for item in db.scalars(select(Program))}
        sections = {item.id: item for item in db.scalars(select(Section))}
        terms = {item.id: item for item in db.scalars(select(AcademicTerm))}
        courses = {item.id: item for item in db.scalars(select(Course))}
        laboratories = {item.id: item for item in db.scalars(select(Laboratory))}
        allowed: dict[UUID, list[Laboratory]] = {}
        for link in db.scalars(select(CourseOfferingAllowedLaboratory).where(CourseOfferingAllowedLaboratory.is_active.is_(True))):
            laboratory = laboratories.get(link.laboratory_id)
            if laboratory:
                allowed.setdefault(link.course_offering_id, []).append(laboratory)
        classrooms = {item.id: item for item in db.scalars(select(Classroom))}
        primary: dict[tuple[UUID, UUID], Classroom] = {}
        assignments = db.scalars(select(SectionClassroomAssignment).where(SectionClassroomAssignment.is_active.is_(True), SectionClassroomAssignment.is_primary.is_(True)))
        for assignment in assignments:
            room = classrooms.get(assignment.classroom_id)
            if room:
                primary.setdefault((assignment.section_id, assignment.academic_term_id), room)
        contexts = []
        for offering in db.scalars(select(CourseOffering)):
            course, section, term = courses.get(offering.course_id), sections.get(offering.section_id), terms.get(offering.academic_term_id)
            if not course or not section or not term:
                continue
            program = programs.get(section.program_id)
            department = departments.get(program.department_id) if program else None
            if not program or not department:
                continue
            selected = laboratories.get(offering.laboratory_override_id)
            allowed_labs = sorted(allowed.get(offering.id, []), key=lambda item: (item.laboratory_code, str(item.id)))
            lab_mode, selected_label, allowed_label = self._laboratory_display(course, offering, selected, allowed_labs, laboratories)
            room = primary.get((section.id, term.id))
            contexts.append({
                "offering": offering, "course": course, "section": section, "program": program,
                "department": department, "term": term,
                "academic_year": term.academic_year, "academic_term": term.term_name,
                "section_department_code": department.department_code, "section_department_name": department.department_name,
                "program_code": program.program_code, "program_name": program.program_name,
                "section_code": section.section_code, "section_name": section.section_name, "student_strength": section.student_strength,
                "course_code": course.course_code, "course_name": course.course_name, "course_type": course.course_type,
                "course_weekly_periods": course.weekly_periods, "weekly_periods_override": offering.weekly_periods_override,
                "weekly_periods": offering.weekly_periods_override or course.weekly_periods,
                "session_duration": course.session_duration, "sessions_per_week": course.sessions_per_week,
                "grouping_mode": course.grouping_mode, "venue_requirement": course.venue_requirement,
                "is_mandatory": offering.is_mandatory, "elective_group": offering.elective_group_name,
                "laboratory_selection_mode": lab_mode, "selected_laboratory": selected_label,
                "allowed_laboratories": allowed_label,
                "primary_classroom": self._room_label(room), "record_status": self._status(offering.is_active),
                "__academic_term_id": term.id, "__department_id": department.id, "__program_id": program.id,
                "__section_id": section.id, "__course_id": course.id, "__course_type": course.course_type,
                "__stable_id": offering.id,
            })
        return contexts

    def _provide_course_offerings(self, db: Session) -> list[dict[str, Any]]:
        return [{key: value for key, value in context.items() if key not in {"offering", "course", "section", "program", "department", "term"}} for context in self._offering_contexts(db)]

    def _provide_theory_faculty_allocations(self, db: Session) -> list[dict[str, Any]]:
        contexts = {item["offering"].id: item for item in self._offering_contexts(db) if not uses_activity_faculty_allocations(item["course"])}
        faculty = {item.id: item for item in db.scalars(select(Faculty))}
        departments = {item.id: item for item in db.scalars(select(Department))}
        rows = []
        for allocation in db.scalars(select(TheoryFacultyAllocation)):
            context, member = contexts.get(allocation.course_offering_id), faculty.get(allocation.faculty_id)
            if context and member:
                rows.append(self._allocation_row(context, member, departments, allocation, None))
        return rows

    def _provide_activity_faculty_allocations(self, db: Session) -> list[dict[str, Any]]:
        contexts = {item["offering"].id: item for item in self._offering_contexts(db) if uses_activity_faculty_allocations(item["course"])}
        faculty = {item.id: item for item in db.scalars(select(Faculty))}
        departments = {item.id: item for item in db.scalars(select(Department))}
        rows = []
        for allocation in db.scalars(select(LaboratoryFacultyAllocation)):
            context, member = contexts.get(allocation.course_offering_id), faculty.get(allocation.faculty_id)
            if context and member:
                rows.append(self._allocation_row(context, member, departments, allocation, faculty.get(allocation.required_with_main_faculty_id)))
        return rows

    def _provide_section_course_faculty(self, db: Session) -> list[dict[str, Any]]:
        contexts = self._offering_contexts(db)
        faculty = {item.id: item for item in db.scalars(select(Faculty))}
        departments = {item.id: item for item in db.scalars(select(Department))}
        theory: dict[UUID, list[TheoryFacultyAllocation]] = {}
        activity: dict[UUID, list[LaboratoryFacultyAllocation]] = {}
        for item in db.scalars(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.is_active.is_(True))):
            theory.setdefault(item.course_offering_id, []).append(item)
        for item in db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.is_active.is_(True))):
            activity.setdefault(item.course_offering_id, []).append(item)
        rows: list[dict[str, Any]] = []
        for context in contexts:
            offering_id = context["offering"].id
            allocations: list[Any] = activity.get(offering_id, []) if uses_activity_faculty_allocations(context["course"]) else theory.get(offering_id, [])
            status = self._allocation_status(context["course"], allocations)
            if not allocations:
                row = self._base_row(context)
                row.update({"faculty_allocation_status": status, "__allocation_status": status})
                rows.append(row)
                continue
            for allocation in allocations:
                member = faculty.get(allocation.faculty_id)
                if not member:
                    continue
                required = faculty.get(getattr(allocation, "required_with_main_faculty_id", None))
                row = self._allocation_row(context, member, departments, allocation, required)
                row.update({"faculty_allocation_status": status, "__allocation_status": status})
                rows.append(row)
        return rows

    def _provide_faculty_workload(self, db: Session) -> list[dict[str, Any]]:
        contexts = self._offering_contexts(db)
        theory_ids = {item["offering"].id for item in contexts if not uses_activity_faculty_allocations(item["course"])}
        activity_ids = {item["offering"].id for item in contexts if uses_activity_faculty_allocations(item["course"])}
        theory_by_term: dict[UUID, dict[UUID, int]] = {}
        activity_by_term: dict[UUID, dict[UUID, int]] = {}
        for term_id in {item["term"].id for item in contexts}:
            theory_by_term[term_id] = configured_faculty_workloads(db, academic_term_id=term_id, offering_ids=theory_ids)
            activity_by_term[term_id] = configured_faculty_workloads(db, academic_term_id=term_id, offering_ids=activity_ids)
        departments = {item.id: item for item in db.scalars(select(Department))}
        rows = []
        terms = list(db.scalars(select(AcademicTerm)))
        for member in db.scalars(select(Faculty)):
            department = departments.get(member.department_id)
            for term in terms:
                theory = theory_by_term.get(term.id, {}).get(member.id, 0)
                activity = activity_by_term.get(term.id, {}).get(member.id, 0)
                total = theory + activity
                workload_status = "UNDERLOAD" if total < member.minimum_weekly_workload else "OVERLOAD" if total > member.maximum_weekly_workload else "WITHIN RANGE"
                rows.append({
                    "faculty_code": member.faculty_code, "faculty_name": member.full_name,
                    "department_code": department.department_code if department else None,
                    "department_name": department.department_name if department else None,
                    "designation": member.designation, "theory_workload": theory, "activity_workload": activity,
                    "total_workload": total, "minimum_workload": member.minimum_weekly_workload,
                    "maximum_workload": member.maximum_weekly_workload,
                    "workload_difference": total - member.minimum_weekly_workload,
                    "remaining_to_maximum": member.maximum_weekly_workload - total,
                    "workload_status": workload_status, "record_status": self._status(member.is_active),
                    "__academic_term_id": term.id, "__department_id": member.department_id,
                    "__faculty_id": member.id, "__designation": member.designation,
                    "__workload_status": workload_status, "__stable_id": f"{term.id}:{member.id}",
                })
        return rows

    def _allocation_row(self, context: dict[str, Any], member: Faculty, departments: dict[UUID, Department], allocation: Any, required: Faculty | None) -> dict[str, Any]:
        row = self._base_row(context)
        department = departments.get(member.department_id)
        role = getattr(allocation, "role_type", "THEORY")
        row.update({
            "faculty_code": member.faculty_code, "faculty_name": member.full_name,
            "faculty_department_code": department.department_code if department else None,
            "faculty_department": department.department_name if department else None,
            "designation": member.designation, "institutional_email": member.institutional_email,
            "phone_number": member.phone_number, "faculty_role": role,
            "required_main_faculty": self._faculty_label(required),
            "alternative_group_code": getattr(allocation, "alternative_group_code", None),
            "minimum_sessions_per_week": getattr(allocation, "minimum_sessions_per_week", None),
            "maximum_sessions_per_week": getattr(allocation, "maximum_sessions_per_week", None),
            "record_status": self._status(allocation.is_active),
            "__faculty_id": member.id, "__faculty_department_id": member.department_id,
            "__designation": member.designation, "__role_type": role, "__stable_id": allocation.id,
        })
        return row

    @staticmethod
    def _base_row(context: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in context.items() if key not in {"offering", "course", "section", "program", "department", "term"}}

    @staticmethod
    def _allocation_status(course: Course, allocations: list[Any]) -> str:
        if not allocations:
            return "MISSING"
        if uses_activity_faculty_allocations(course):
            return "COMPLETE" if any(item.role_type == "MAIN" for item in allocations) else "PARTIAL"
        return "COMPLETE" if len(allocations) == 1 else "PARTIAL"

    @staticmethod
    def _laboratory_display(course: Course, offering: CourseOffering, selected: Laboratory | None, allowed: list[Laboratory], laboratories: dict[UUID, Laboratory]) -> tuple[str | None, str | None, str | None]:
        if course.venue_requirement in {"CLASSROOM_ONLY", "NO_FIXED_VENUE"}:
            return None, None, None
        mode = offering.laboratory_selection_mode
        selected_label = ReportService._lab_label(selected)
        allowed_values = allowed
        if mode == "AUTO":
            eligible = [laboratories.get(item) for item in course.eligible_laboratory_ids]
            allowed_values = [item for item in eligible if item]
            return "Automatic", "Any eligible laboratory", ReportService._lab_set(allowed_values)
        if mode == "PREFERRED": return "Preferred", selected_label, ReportService._lab_set(allowed_values)
        if mode == "FIXED": return "Required", selected_label, selected_label
        if mode == "RESTRICTED": return "Restricted", None, ReportService._lab_set(allowed_values)
        return mode, selected_label, ReportService._lab_set(allowed_values)

    @staticmethod
    def _status(active: bool) -> str: return "Active" if active else "Inactive"
    @staticmethod
    def _faculty_label(item: Faculty | None) -> str | None: return f"{item.faculty_code} • {item.full_name}" if item else None
    @staticmethod
    def _lab_label(item: Laboratory | None) -> str | None: return f"{item.laboratory_code} • {item.laboratory_name}" if item else None
    @staticmethod
    def _lab_set(items: list[Laboratory]) -> str | None:
        values = sorted({ReportService._lab_label(item) for item in items if item}, key=str)
        return ", ".join(values) if values else None
    @staticmethod
    def _room_label(item: Classroom | None) -> str | None:
        return f"{item.room_number}{f' • {item.room_name}' if item and item.room_name else ''}" if item else None


report_service = ReportService()
