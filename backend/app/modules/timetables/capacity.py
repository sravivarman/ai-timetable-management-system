"""Student-demand helpers for capacity-constrained physical resources."""

from sqlalchemy import select

from app.modules.combined_teaching.models import CombinedTeachingEvent, CombinedTeachingGroupMember
from app.modules.course_offerings.models import CourseOffering
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.sections.models import Section


def combined_event_demand(db, combined_event_id) -> int:
    event = db.get(CombinedTeachingEvent, combined_event_id)
    if not event:
        return 0
    section_ids = list(db.scalars(
        select(CourseOffering.section_id)
        .join(CombinedTeachingGroupMember, CombinedTeachingGroupMember.course_offering_id == CourseOffering.id)
        .where(
            CombinedTeachingGroupMember.combined_teaching_group_id == event.combined_teaching_group_id,
            CombinedTeachingGroupMember.is_active.is_(True),
        )
        .distinct()
    ))
    return sum(db.scalars(select(Section.student_strength).where(Section.id.in_(section_ids))))


def entry_capacity_demand(db, entry_or_payload) -> int:
    """Return actual participants, never a solver-side equal division estimate."""
    combined_event_id = getattr(entry_or_payload, "combined_teaching_event_id", None)
    if combined_event_id:
        return combined_event_demand(db, combined_event_id)
    batch_id = getattr(entry_or_payload, "student_batch_id", None)
    if batch_id:
        batch = db.get(StudentBatch, batch_id)
        return int(batch.student_count) if batch else 0
    section = db.get(Section, getattr(entry_or_payload, "section_id", None))
    return int(section.student_strength) if section else 0


def logical_capacity_key(entry) -> tuple:
    """Backward-compatible child entries of one combined event consume capacity once."""
    return ("combined", entry.combined_teaching_event_id) if entry.combined_teaching_event_id else ("entry", entry.id)
