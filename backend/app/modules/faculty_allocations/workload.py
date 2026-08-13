"""Configured faculty workload derived from physical teaching occurrences.

Course ``weekly_periods`` is a per-student-group contact requirement.  Faculty
workload is different: for grouped activities it counts every group-specific
physical occurrence.  Synchronized rotations are therefore counted from their
explicit assignments, while ordinary grouped offerings use the effective group
count.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.combined_teaching.models import CombinedTeachingGroup, CombinedTeachingGroupMember
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.laboratory_batches.models import (
    LaboratoryBatchConfiguration,
    LaboratoryRotationAssignment,
    LaboratoryRotationBlock,
    LaboratoryRotationGroup,
)
from app.modules.programs.models import Program
from app.modules.sections.models import Section


def configured_faculty_workloads(
    db: Session,
    *,
    faculty_id: UUID | None = None,
    academic_term_id: UUID | None = None,
    department_id: UUID | None = None,
    offering_ids: set[UUID] | None = None,
) -> dict[UUID, int]:
    """Return configured physical teaching periods per faculty member.

    This is a pre-solver preview. Generated timetable reports should continue
    to use persisted entries, which are the final source of actual occupancy.
    """

    offering_query = (
        select(CourseOffering, Course)
        .join(Course, Course.id == CourseOffering.course_id)
        .join(Section, Section.id == CourseOffering.section_id)
        .join(Program, Program.id == Section.program_id)
        .where(CourseOffering.is_active.is_(True), Course.is_active.is_(True), Course.counts_toward_workload.is_(True))
    )
    if academic_term_id:
        offering_query = offering_query.where(CourseOffering.academic_term_id == academic_term_id)
    if department_id:
        offering_query = offering_query.where(Program.department_id == department_id)
    if offering_ids is not None:
        if not offering_ids:
            return {}
        offering_query = offering_query.where(CourseOffering.id.in_(offering_ids))

    offerings = {offering.id: (offering, course) for offering, course in db.execute(offering_query)}
    if not offerings:
        return {}

    results: dict[UUID, int] = {}

    def add(member_id: UUID | None, periods: int) -> None:
        if member_id is None or (faculty_id is not None and member_id != faculty_id):
            return
        results[member_id] = results.get(member_id, 0) + periods

    rotation_query = (
        select(LaboratoryRotationAssignment)
        .join(LaboratoryRotationBlock, LaboratoryRotationBlock.id == LaboratoryRotationAssignment.rotation_block_id)
        .join(LaboratoryRotationGroup, LaboratoryRotationGroup.id == LaboratoryRotationAssignment.rotation_group_id)
        .where(
            LaboratoryRotationAssignment.course_offering_id.in_(offerings),
            LaboratoryRotationAssignment.is_active.is_(True),
            LaboratoryRotationBlock.is_active.is_(True),
            LaboratoryRotationGroup.is_active.is_(True),
        )
    )
    rotation_assignments = list(db.scalars(rotation_query))
    rotated_offering_ids = {assignment.course_offering_id for assignment in rotation_assignments}
    for assignment in rotation_assignments:
        _, course = offerings[assignment.course_offering_id]
        duration = int(assignment.session_duration or course.session_duration)
        add(assignment.main_faculty_id, duration)
        for supporting_id in assignment.supporting_faculty_ids or []:
            add(UUID(str(supporting_id)), duration)

    configuration_by_offering = {
        configuration.course_offering_id: configuration
        for configuration in db.scalars(
            select(LaboratoryBatchConfiguration).where(
                LaboratoryBatchConfiguration.course_offering_id.in_(offerings),
                LaboratoryBatchConfiguration.is_active.is_(True),
            )
        )
    }
    combined_by_offering = {
        member.course_offering_id: group
        for member, group in db.execute(
            select(CombinedTeachingGroupMember, CombinedTeachingGroup)
            .join(CombinedTeachingGroup, CombinedTeachingGroup.id == CombinedTeachingGroupMember.combined_teaching_group_id)
            .where(
                CombinedTeachingGroupMember.course_offering_id.in_(offerings),
                CombinedTeachingGroupMember.is_active.is_(True),
                CombinedTeachingGroup.is_active.is_(True),
            )
        )
    }
    combined_seen: set[UUID] = set()
    for allocation_model in (TheoryFacultyAllocation, LaboratoryFacultyAllocation):
        allocations = db.scalars(
            select(allocation_model).where(
                allocation_model.course_offering_id.in_(offerings),
                allocation_model.is_active.is_(True),
            )
        )
        for allocation in allocations:
            if allocation.course_offering_id in rotated_offering_ids:
                continue
            offering, course = offerings[allocation.course_offering_id]
            combined = combined_by_offering.get(offering.id)
            if combined and allocation.faculty_id == combined.faculty_id:
                if combined.id in combined_seen:
                    continue
                combined_seen.add(combined.id)
                multiplier = 1
            else:
                configuration = configuration_by_offering.get(offering.id)
                group_count = configuration.number_of_groups if configuration else course.default_group_count
                multiplier = group_count if course.grouping_mode == "GROUPED" else 1
            add(allocation.faculty_id, int(offering.weekly_periods_override or course.weekly_periods) * multiplier)
    return results
