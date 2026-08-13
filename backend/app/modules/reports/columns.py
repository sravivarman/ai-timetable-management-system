"""Shared report-column catalogue used by previews and every exporter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    group: str
    data_type: str = "text"
    sortable: bool = True
    default_width: int = 18
    alignment: str = "left"


def _column(key: str, label: str, group: str, data_type: str = "text", width: int = 18, alignment: str = "left") -> ReportColumn:
    return ReportColumn(key, label, group, data_type, True, width, alignment)


COLUMNS = {column.key: column for column in (
    _column("academic_year", "Academic Year", "Academic", width=14),
    _column("academic_term", "Academic Term", "Academic", width=16),
    _column("department_code", "Department Code", "Academic", width=16),
    _column("department_name", "Department Name", "Academic", width=30),
    _column("section_department_code", "Section Department Code", "Academic", width=20),
    _column("section_department_name", "Section Department", "Academic", width=30),
    _column("program_code", "Program Code", "Academic", width=18),
    _column("program_name", "Program Name", "Academic", width=34),
    _column("section_code", "Section", "Academic", width=16),
    _column("section_name", "Section Name", "Academic", width=14),
    _column("student_strength", "Student Strength", "Academic", "integer", 16, "right"),
    _column("course_code", "Course Code", "Course", width=16),
    _column("course_name", "Course Name", "Course", width=34),
    _column("course_type", "Course Type", "Course", width=16),
    _column("course_weekly_periods", "Course Weekly Periods", "Course", "integer", 20, "right"),
    _column("weekly_periods_override", "Offering Override", "Course", "integer", 18, "right"),
    _column("weekly_periods", "Effective Weekly Periods", "Course", "integer", 22, "right"),
    _column("session_duration", "Session Duration", "Course", "integer", 17, "right"),
    _column("sessions_per_week", "Sessions per Week", "Course", "integer", 18, "right"),
    _column("grouping_mode", "Grouping Mode", "Course", width=18),
    _column("venue_requirement", "Venue Requirement", "Venue", width=20),
    _column("is_mandatory", "Mandatory", "Course", "boolean", 12, "center"),
    _column("elective_group", "Elective Group", "Course", width=20),
    _column("laboratory_selection_mode", "Laboratory Selection Mode", "Venue", width=24),
    _column("selected_laboratory", "Selected Laboratory", "Venue", width=28),
    _column("allowed_laboratories", "Allowed Laboratories", "Venue", width=34),
    _column("primary_classroom", "Primary Classroom", "Venue", width=24),
    _column("faculty_code", "Faculty ID", "Faculty", width=15),
    _column("faculty_name", "Faculty Name", "Faculty", width=28),
    _column("faculty_department_code", "Faculty Department Code", "Faculty", width=22),
    _column("faculty_department", "Faculty Department", "Faculty", width=30),
    _column("designation", "Designation", "Faculty", width=22),
    _column("institutional_email", "Institutional Email", "Faculty", width=30),
    _column("phone_number", "Phone Number", "Faculty", width=18),
    _column("faculty_role", "Faculty Role", "Allocation", width=16),
    _column("required_main_faculty", "Required Main Faculty", "Allocation", width=30),
    _column("alternative_group_code", "Alternative Group", "Allocation", width=20),
    _column("minimum_sessions_per_week", "Minimum Sessions per Week", "Allocation", "integer", 24, "right"),
    _column("maximum_sessions_per_week", "Maximum Sessions per Week", "Allocation", "integer", 24, "right"),
    _column("faculty_allocation_status", "Faculty Allocation Status", "Allocation", width=24),
    _column("theory_workload", "Theory Workload", "Workload", "number", 18, "right"),
    _column("activity_workload", "Activity Workload", "Workload", "number", 19, "right"),
    _column("total_workload", "Total Workload", "Workload", "number", 17, "right"),
    _column("minimum_workload", "Minimum Workload", "Workload", "number", 19, "right"),
    _column("maximum_workload", "Maximum Workload", "Workload", "number", 19, "right"),
    _column("workload_difference", "Difference from Minimum", "Workload", "number", 23, "right"),
    _column("remaining_to_maximum", "Remaining to Maximum", "Workload", "number", 23, "right"),
    _column("workload_status", "Workload Status", "Workload", width=18),
    _column("record_status", "Status", "Record", width=12),
)}
