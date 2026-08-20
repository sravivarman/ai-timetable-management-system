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
    _column("slot_code", "Slot Code", "Slot", width=14),
    _column("slot_name", "Slot Name", "Slot", width=24),
    _column("semester_required", "Semester Required Sessions", "Progress", "integer", 24, "right"),
    _column("allocated_to_slots", "Allocated to Slots", "Progress", "integer", 18, "right"),
    _column("remaining_to_allocate", "Remaining to Allocate", "Progress", "integer", 20, "right"),
    _column("over_allocated", "Over Allocated", "Progress", "integer", 16, "right"),
    _column("scheduled_sessions", "Scheduled Sessions", "Progress", "integer", 18, "right"),
    _column("approved_sessions", "Approved Sessions", "Progress", "integer", 18, "right"),
    _column("published_sessions", "Published Sessions", "Progress", "integer", 19, "right"),
    _column("remaining_to_schedule", "Remaining to Schedule", "Progress", "integer", 21, "right"),
    _column("remaining_to_publish", "Remaining to Publish", "Progress", "integer", 20, "right"),
    _column("reconciliation_status", "Reconciliation Status", "Progress", width=21),
    _column("progress_status", "Progress Status", "Progress", width=18),
    _column("sessions_required", "Sessions Required", "Progress", "integer", 18, "right"),
    _column("requirement_status", "Requirement Status", "Progress", width=20),
    _column("theory_sessions", "Theory Sessions", "Slot Workload", "integer", 17, "right"),
    _column("theory_periods", "Theory Periods", "Slot Workload", "integer", 16, "right"),
    _column("activity_sessions", "Activity Sessions", "Slot Workload", "integer", 18, "right"),
    _column("activity_periods", "Activity Periods", "Slot Workload", "integer", 17, "right"),
    _column("total_periods", "Total Slot Periods", "Slot Workload", "integer", 18, "right"),
    _column("main_activity_periods", "Main Activity Periods", "Slot Workload", "integer", 21, "right"),
    _column("supporting_activity_periods", "Supporting Activity Periods", "Slot Workload", "integer", 26, "right"),
    _column("minimum_weekly_workload", "Weekly Minimum (Reference)", "Slot Workload", "integer", 26, "right"),
    _column("maximum_weekly_workload", "Weekly Maximum (Reference)", "Slot Workload", "integer", 26, "right"),
    _column("slot_working_date_count", "Slot Working Dates", "Slot Workload", "integer", 18, "right"),
    _column("average_periods_per_working_date", "Average Periods per Date", "Slot Workload", "number", 23, "right"),
    _column("maximum_periods_on_any_slot_date", "Maximum Periods on a Date", "Slot Workload", "integer", 26, "right"),
    _column("date", "Date", "Timetable", width=14),
    _column("day", "Day", "Timetable", width=12),
    _column("period", "Period", "Timetable", "integer", 10, "right"),
    _column("student_group", "Student Group", "Timetable", width=16),
    _column("venue_type", "Venue Type", "Timetable", width=14),
    _column("venue_code", "Venue", "Timetable", width=18),
    _column("entry_type", "Entry Type", "Timetable", width=14),
    _column("duration", "Duration", "Timetable", "integer", 12, "right"),
    _column("version", "Version", "Timetable", width=14),
    _column("version_status", "Version Status", "Timetable", width=16),
)}
