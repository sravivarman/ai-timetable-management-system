"""Allow-listed administrative report definitions."""

from dataclasses import dataclass

from app.modules.reports.columns import COLUMNS


@dataclass(frozen=True)
class ReportFilter:
    key: str
    label: str
    control: str = "entity"
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    description: str
    allowed_columns: tuple[str, ...]
    default_columns: tuple[str, ...]
    filters: tuple[ReportFilter, ...]
    default_sort: tuple[tuple[str, str], ...]
    supported_formats: tuple[str, ...] = ("xlsx", "csv", "docx", "pdf")
    layout_type: str = "TABULAR"


ACADEMIC = (
    "academic_year", "academic_term", "section_department_code", "section_department_name",
    "program_code", "program_name", "section_code", "section_name",
)
COURSE = (
    "course_code", "course_name", "course_type", "course_weekly_periods",
    "weekly_periods_override", "weekly_periods", "session_duration", "sessions_per_week",
    "grouping_mode", "venue_requirement", "is_mandatory", "elective_group",
)
VENUE = ("laboratory_selection_mode", "selected_laboratory", "allowed_laboratories", "primary_classroom")
FACULTY = (
    "faculty_code", "faculty_name", "faculty_department_code", "faculty_department",
    "designation", "institutional_email", "phone_number",
)
ALLOCATION = (
    "faculty_role", "required_main_faculty", "alternative_group_code",
    "minimum_sessions_per_week", "maximum_sessions_per_week", "faculty_allocation_status",
)

TERM = ReportFilter("academic_term_id", "Academic Term")
DEPARTMENT = ReportFilter("department_id", "Department")
PROGRAM = ReportFilter("program_id", "Program")
SECTION = ReportFilter("section_id", "Section")
COURSE_FILTER = ReportFilter("course_id", "Course")
FACULTY_FILTER = ReportFilter("faculty_id", "Faculty")
FACULTY_DEPARTMENT = ReportFilter("faculty_department_id", "Faculty Department")
DESIGNATION = ReportFilter("designation", "Designation", "enum", ("Assistant Professor", "Associate Professor", "Professor"))
STATUS = ReportFilter("status", "Status", "enum", ("ACTIVE", "INACTIVE", "ALL"))
COURSE_TYPE = ReportFilter("course_type", "Course Type", "enum", ("THEORY", "LABORATORY", "PRACTICAL", "CDC", "LSM", "MINI_PROJECT", "PROJECT"))


REPORTS = {
    definition.key: definition
    for definition in (
        ReportDefinition(
            "faculty_master", "Faculty Master", "Faculty directory and configured workload limits.",
            ("faculty_code", "faculty_name", "department_code", "department_name", "designation", "institutional_email", "phone_number", "minimum_workload", "maximum_workload", "record_status"),
            ("faculty_code", "faculty_name", "department_name", "designation", "institutional_email", "phone_number"),
            (DEPARTMENT, DESIGNATION, FACULTY_FILTER, STATUS),
            (("department_name", "asc"), ("faculty_name", "asc"), ("faculty_code", "asc")),
        ),
        ReportDefinition(
            "course_offerings", "Course Offerings", "Term-scoped course offerings and venue requirements.",
            ACADEMIC + COURSE + VENUE + ("record_status",),
            ("section_code", "course_code", "course_name", "course_type", "weekly_periods", "laboratory_selection_mode", "record_status"),
            (TERM, DEPARTMENT, PROGRAM, SECTION, COURSE_FILTER, COURSE_TYPE, STATUS),
            (("section_department_name", "asc"), ("section_code", "asc"), ("course_code", "asc")),
        ),
        ReportDefinition(
            "theory_faculty_allocations", "Theory Faculty Allocations", "One row per ordinary course-offering faculty allocation.",
            ACADEMIC + COURSE + FACULTY + ("record_status",),
            ("section_code", "course_code", "course_name", "faculty_code", "faculty_name", "designation"),
            (TERM, DEPARTMENT, PROGRAM, SECTION, COURSE_FILTER, FACULTY_FILTER, FACULTY_DEPARTMENT, DESIGNATION, STATUS),
            (("section_department_name", "asc"), ("section_code", "asc"), ("course_code", "asc"), ("faculty_name", "asc")),
        ),
        ReportDefinition(
            "activity_faculty_allocations", "Activity Faculty Allocations", "Laboratory and practical MAIN/SUPPORTING allocations.",
            ACADEMIC + COURSE + FACULTY + ALLOCATION[:-1] + ("record_status",),
            ("section_code", "course_code", "course_name", "faculty_code", "faculty_name", "faculty_role"),
            (TERM, DEPARTMENT, PROGRAM, SECTION, COURSE_FILTER, COURSE_TYPE, FACULTY_FILTER, ReportFilter("role_type", "Role Type", "enum", ("MAIN", "SUPPORTING")), STATUS),
            (("section_department_name", "asc"), ("section_code", "asc"), ("course_code", "asc"), ("faculty_role", "asc"), ("faculty_name", "asc")),
        ),
        ReportDefinition(
            "section_course_faculty", "Section-wise Course & Faculty Allocation", "Pre-solver completeness view retaining unallocated offerings.",
            ACADEMIC + COURSE + FACULTY + ALLOCATION + VENUE + ("record_status",),
            ("section_code", "course_code", "course_name", "course_type", "faculty_code", "faculty_name", "faculty_role", "faculty_allocation_status"),
            (TERM, DEPARTMENT, PROGRAM, SECTION, COURSE_FILTER, COURSE_TYPE, ReportFilter("allocation_status", "Faculty Allocation Status", "enum", ("COMPLETE", "PARTIAL", "MISSING")), STATUS),
            (("section_department_name", "asc"), ("section_code", "asc"), ("course_code", "asc"), ("faculty_role", "asc"), ("faculty_name", "asc")),
        ),
        ReportDefinition(
            "faculty_workload", "Faculty Workload", "Planned workload from the authoritative configured-workload service.",
            ("faculty_code", "faculty_name", "department_code", "department_name", "designation", "theory_workload", "activity_workload", "total_workload", "minimum_workload", "maximum_workload", "workload_difference", "remaining_to_maximum", "workload_status", "record_status"),
            ("faculty_code", "faculty_name", "department_name", "designation", "theory_workload", "activity_workload", "total_workload", "minimum_workload", "maximum_workload", "workload_status"),
            (TERM, DEPARTMENT, FACULTY_FILTER, DESIGNATION, ReportFilter("workload_status", "Workload Status", "enum", ("UNDERLOAD", "WITHIN RANGE", "OVERLOAD")), STATUS),
            (("department_name", "asc"), ("faculty_name", "asc"), ("faculty_code", "asc")),
        ),
    )
}


def validate_registry() -> None:
    for definition in REPORTS.values():
        unknown = set(definition.allowed_columns) - set(COLUMNS)
        if unknown:
            raise RuntimeError(f"Unknown report columns for {definition.key}: {sorted(unknown)}")


validate_registry()
