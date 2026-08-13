from dataclasses import dataclass

from app.modules.facilities.models import Classroom, Laboratory
from app.modules.faculty.models import Faculty


@dataclass(frozen=True)
class ResourceRegistration:
    resource_type: str
    model: type
    code_field: str
    name_field: str
    endpoint: str
    read_permission: tuple[str, str]
    manage_permission: tuple[str, str]
    concrete_type: str


def _room(kind: str) -> ResourceRegistration:
    return ResourceRegistration(kind, Classroom, "room_number", "room_name", "/classrooms", ("classrooms", "read"), ("classrooms", "manage"), "CLASSROOM")


RESOURCE_REGISTRY = {
    "CLASSROOM": _room("CLASSROOM"),
    "SEMINAR_HALL": _room("SEMINAR_HALL"),
    "SMART_CLASSROOM": _room("SMART_CLASSROOM"),
    "DRAWING_HALL": _room("DRAWING_HALL"),
    "WORKSHOP_ROOM": _room("WORKSHOP_ROOM"),
    "WORKSHOP": _room("WORKSHOP"),
    "GUEST_LECTURE_HALL": _room("GUEST_LECTURE_HALL"),
    "GUEST_HALL": _room("GUEST_HALL"),
    "LABORATORY": ResourceRegistration("LABORATORY", Laboratory, "laboratory_code", "laboratory_name", "/laboratories", ("laboratory_blocks", "read"), ("laboratory_blocks", "manage"), "LABORATORY"),
    "FACULTY": ResourceRegistration("FACULTY", Faculty, "faculty_code", "full_name", "/faculty", ("faculty_availability", "read"), ("faculty_availability", "manage"), "FACULTY"),
    "VISITING_FACULTY": ResourceRegistration("VISITING_FACULTY", Faculty, "faculty_code", "full_name", "/faculty", ("faculty_availability", "read"), ("faculty_availability", "manage"), "FACULTY"),
}


def registration(resource_type: str) -> ResourceRegistration:
    return RESOURCE_REGISTRY.get(resource_type.upper())
