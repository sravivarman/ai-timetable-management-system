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
SLOT = ReportFilter("scheduling_slot_id", "Scheduling Slot")
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
        ReportDefinition(
            "semester_session_progress", "Semester Session Progress", "Planned, allocated, scheduled and immutable approved/published academic-session progress.",
            ("academic_year","academic_term","department_code","department_name","program_code","program_name","section_code","section_name","course_code","course_name","course_type","semester_required","allocated_to_slots","scheduled_sessions","approved_sessions","published_sessions","remaining_to_allocate","remaining_to_schedule","remaining_to_publish","reconciliation_status","progress_status"),
            ("academic_year","academic_term","department_code","program_code","section_code","course_code","course_name","semester_required","allocated_to_slots","scheduled_sessions","approved_sessions","remaining_to_allocate","remaining_to_schedule","reconciliation_status","progress_status"),
            (TERM,DEPARTMENT,PROGRAM,SECTION,COURSE_FILTER,COURSE_TYPE,ReportFilter("reconciliation_status","Reconciliation Status","enum",("NOT_CONFIGURED","UNDER_ALLOCATED","FULLY_ALLOCATED","OVER_ALLOCATED")),ReportFilter("progress_status","Progress Status","enum",("NOT_STARTED","IN_PROGRESS","COMPLETE"))),
            (("section_code","asc"),("course_code","asc")),
        ),
        ReportDefinition(
            "slot_session_progress", "Slot Session Progress", "Academic-session completion for one or more actual-date Scheduling Slots.",
            ("academic_year","academic_term","slot_code","slot_name","department_code","program_code","section_code","course_code","course_name","course_type","sessions_required","scheduled_sessions","approved_sessions","published_sessions","remaining_to_schedule","progress_status"),
            ("academic_term","slot_code","section_code","course_code","course_name","sessions_required","scheduled_sessions","approved_sessions","remaining_to_schedule","progress_status"),
            (TERM,SLOT,DEPARTMENT,PROGRAM,SECTION,COURSE_FILTER,COURSE_TYPE,ReportFilter("progress_status","Progress Status","enum",("NOT_STARTED","IN_PROGRESS","COMPLETE"))),
            (("slot_code","asc"),("section_code","asc"),("course_code","asc")),
        ),
        ReportDefinition(
            "slot_requirement_completeness", "Slot Requirement Completeness", "Missing, explicit-zero, positive, and invalid Slot requirements without conflation.",
            ("academic_year","academic_term","slot_code","slot_name","section_code","course_code","course_name","course_type","sessions_required","requirement_status"),
            ("academic_term","slot_code","section_code","course_code","course_name","sessions_required","requirement_status"),
            (TERM,SLOT,DEPARTMENT,PROGRAM,SECTION,COURSE_FILTER,COURSE_TYPE,ReportFilter("requirement_status","Requirement Status","enum",("MISSING","CONFIGURED_ZERO","CONFIGURED_POSITIVE","INVALID"))),
            (("slot_code","asc"),("section_code","asc"),("course_code","asc")),
        ),
        ReportDefinition(
            "slot_faculty_workload", "Slot Faculty Workload", "Actual workload across a variable-length Slot; weekly limits are reference values only.",
            ("academic_year","academic_term","slot_code","slot_name","faculty_code","faculty_name","faculty_department","designation","theory_sessions","theory_periods","activity_sessions","activity_periods","total_periods","main_activity_periods","supporting_activity_periods","minimum_weekly_workload","maximum_weekly_workload","slot_working_date_count","average_periods_per_working_date","maximum_periods_on_any_slot_date"),
            ("academic_term","slot_code","faculty_code","faculty_name","faculty_department","theory_periods","activity_periods","total_periods","slot_working_date_count","average_periods_per_working_date","maximum_periods_on_any_slot_date"),
            (TERM,SLOT,DEPARTMENT,FACULTY_FILTER,DESIGNATION),
            (("slot_code","asc"),("faculty_name","asc")),
        ),
        ReportDefinition(
            "slot_timetable", "Slot Timetable", "Actual-date, business-readable long-form Slot timetable suitable for CSV and fixed-layout source data.",
            ("academic_year","academic_term","slot_code","slot_name","date","day","period","section_code","student_group","course_code","course_name","course_type","faculty_code","faculty_name","faculty_role","venue_type","venue_code","entry_type","duration","version","version_status"),
            ("slot_code","date","day","period","section_code","student_group","course_code","course_name","faculty_code","venue_type","venue_code","entry_type","duration","version","version_status"),
            (TERM,SLOT,DEPARTMENT,PROGRAM,SECTION,COURSE_FILTER,COURSE_TYPE,FACULTY_FILTER),
            (("date","asc"),("period","asc"),("section_code","asc"),("course_code","asc")),
            layout_type="SLOT_TIMETABLE",
        ),
    )
}


def validate_registry() -> None:
    for definition in REPORTS.values():
        unknown = set(definition.allowed_columns) - set(COLUMNS)
        if unknown:
            raise RuntimeError(f"Unknown report columns for {definition.key}: {sorted(unknown)}")


validate_registry()
