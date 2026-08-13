"""Single source of truth for offering-level laboratory candidate resolution."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.facilities.models import Laboratory


def course_eligible_laboratory_ids(course: Course) -> list[UUID]:
    """Return technical course eligibility, retaining default-only legacy fixtures."""
    ids = list(course.eligible_laboratory_ids)
    if not ids and course.default_laboratory_id:
        ids = [course.default_laboratory_id]
    return ids


def effective_laboratory_ids(course: Course, offering: CourseOffering) -> list[UUID]:
    """Resolve the hard candidate IDs before active/shareability filtering."""
    course_ids = course_eligible_laboratory_ids(course)
    course_set = set(course_ids)
    if offering.laboratory_selection_mode == "FIXED":
        return [offering.laboratory_override_id] if offering.laboratory_override_id in course_set else []
    if offering.laboratory_selection_mode == "RESTRICTED":
        return [item for item in offering.allowed_laboratory_ids if item in course_set]
    return course_ids


def resolve_effective_laboratories(db: Session, course: Course, offering: CourseOffering) -> list[Laboratory]:
    """Return deterministic, active and ownership-compatible effective candidates."""
    ids = effective_laboratory_ids(course, offering)
    if not ids:
        return []
    laboratories = {
        laboratory.id: laboratory
        for laboratory in db.scalars(
            select(Laboratory).where(Laboratory.id.in_(ids), Laboratory.is_active.is_(True))
        )
        if laboratory.owning_department_id == course.offering_department_id
        or laboratory.is_shareable_across_departments
    }
    return [laboratories[laboratory_id] for laboratory_id in ids if laboratory_id in laboratories]
