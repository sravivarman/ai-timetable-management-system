"""Faculty-allocation capability rules shared by APIs, validation, and solving.

The historical ``laboratory_faculty_allocations`` name is retained for API and
database compatibility.  It stores the richer allocation contract used by
laboratory and practical activities.
"""

ACTIVITY_FACULTY_COURSE_TYPES = frozenset({"LABORATORY", "PRACTICAL"})


def uses_activity_faculty_allocations(course_or_type) -> bool:
    course_type = getattr(course_or_type, "course_type", course_or_type)
    return course_type in ACTIVITY_FACULTY_COURSE_TYPES

