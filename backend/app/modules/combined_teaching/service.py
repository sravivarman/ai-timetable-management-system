"""Compatibility and lifecycle rules for combined teaching."""

from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.course_offerings.laboratories import resolve_effective_laboratories
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.facilities.models import Classroom, Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.sections.models import Section
from .models import CombinedTeachingGroup, CombinedTeachingGroupMember
from .repository import combined_teaching_repository
from .schemas import CombinedTeachingGroupCreate, CombinedTeachingGroupUpdate


class CombinedTeachingService:
    def _values(self, db: Session, data: dict, exclude_id: UUID | None = None):
        term = db.get(AcademicTerm, data["academic_term_id"])
        if not term or not term.is_active:
            raise HTTPException(422, "COMBINED_TEACHING_TERM_MISMATCH: academic term must be active")
        course = db.get(Course, data["course_id"])
        if not course or not course.is_active:
            raise HTTPException(422, "COMBINED_TEACHING_COURSE_MISMATCH: course must be active")
        faculty = db.get(Faculty, data["faculty_id"])
        if not faculty or not faculty.is_active:
            raise HTTPException(422, "COMBINED_TEACHING_FACULTY_MISSING: faculty must be active")
        ids = data.get("course_offering_ids") or []
        if len(ids) < 2:
            raise HTTPException(422, "COMBINED_TEACHING_MINIMUM_SECTIONS: select at least two offerings")
        if len(set(ids)) != len(ids):
            raise HTTPException(422, "COMBINED_TEACHING_DUPLICATE_SECTION: duplicate offering")
        offerings = list(db.scalars(select(CourseOffering).where(CourseOffering.id.in_(ids))))
        if len(offerings) != len(ids) or any(not row.is_active for row in offerings):
            raise HTTPException(422, "COMBINED_TEACHING_INCOMPLETE: every offering must be active")
        if any(row.academic_term_id != term.id for row in offerings):
            raise HTTPException(422, "COMBINED_TEACHING_TERM_MISMATCH: offerings must use the selected term")
        if any(row.course_id != course.id for row in offerings):
            raise HTTPException(422, "COMBINED_TEACHING_COURSE_MISMATCH: offerings must use the same course")
        sections = [db.get(Section, row.section_id) for row in offerings]
        if any(not section or not section.is_active or section.academic_term_id != term.id for section in sections):
            raise HTTPException(422, "COMBINED_TEACHING_TERM_MISMATCH: sections must be active in the selected term")
        if len({section.id for section in sections}) != len(sections):
            raise HTTPException(422, "COMBINED_TEACHING_DUPLICATE_SECTION: each section may participate once")
        if any(section.student_strength is None or section.student_strength <= 0 for section in sections):
            raise HTTPException(422, "COMBINED_TEACHING_SECTION_STRENGTH_MISSING: section strength must be positive")
        effective = {row.weekly_periods_override or course.weekly_periods for row in offerings}
        if len(effective) != 1 or next(iter(effective)) != course.session_duration * course.sessions_per_week:
            raise HTTPException(422, "COMBINED_TEACHING_SESSION_MISMATCH: weekly and session patterns must match")
        allocation_model = LaboratoryFacultyAllocation if course.course_type == "LABORATORY" else TheoryFacultyAllocation
        allocation_filters = [allocation_model.course_offering_id.in_(ids), allocation_model.faculty_id == faculty.id, allocation_model.is_active.is_(True)]
        if allocation_model is LaboratoryFacultyAllocation:
            allocation_filters.append(LaboratoryFacultyAllocation.role_type == "MAIN")
        allocated = set(db.scalars(select(allocation_model.course_offering_id).where(*allocation_filters)))
        if allocated != set(ids):
            raise HTTPException(422, "COMBINED_TEACHING_FACULTY_MISMATCH: selected faculty must be allocated to every offering")
        other = db.scalar(select(CombinedTeachingGroupMember).join(CombinedTeachingGroup).where(CombinedTeachingGroupMember.course_offering_id.in_(ids), CombinedTeachingGroupMember.is_active.is_(True), CombinedTeachingGroup.is_active.is_(True), CombinedTeachingGroup.id != exclude_id))
        if other:
            raise HTTPException(409, "COMBINED_TEACHING_DUPLICATE_SECTION: an offering already belongs to an active combined group")
        classroom = db.get(Classroom, data.get("preferred_classroom_id")) if data.get("preferred_classroom_id") else None
        laboratory = db.get(Laboratory, data.get("preferred_laboratory_id")) if data.get("preferred_laboratory_id") else None
        if classroom and not classroom.is_active or laboratory and not laboratory.is_active:
            raise HTTPException(422, "COMBINED_TEACHING_NO_ELIGIBLE_VENUE: preferred venue must be active")
        if laboratory:
            member_candidate_sets = [
                {candidate.id for candidate in resolve_effective_laboratories(db, course, offering)}
                for offering in offerings
            ]
            eligible_ids = set.intersection(*member_candidate_sets) if member_candidate_sets else set()
            if laboratory.id not in eligible_ids:
                raise HTTPException(422, "COMBINED_TEACHING_NO_ELIGIBLE_VENUE: laboratory is not permitted by every member offering")
            if laboratory.owning_department_id != course.offering_department_id and not laboratory.is_shareable_across_departments:
                raise HTTPException(422, "COMBINED_TEACHING_NO_ELIGIBLE_VENUE: cross-department laboratory is not shareable")
        venue = course.venue_requirement
        if venue == "CLASSROOM_ONLY" and (not classroom or laboratory):
            raise HTTPException(422, "COMBINED_TEACHING_ROOM_MISSING: classroom-only combined teaching requires a classroom")
        if venue == "LABORATORY_ONLY" and (not laboratory or classroom):
            raise HTTPException(422, "COMBINED_TEACHING_ROOM_MISSING: laboratory-only combined teaching requires a laboratory")
        if venue == "CLASSROOM_OR_LABORATORY" and bool(classroom) == bool(laboratory):
            raise HTTPException(422, "COMBINED_TEACHING_NO_ELIGIBLE_VENUE: select exactly one preferred venue")
        combined_strength = sum(section.student_strength for section in sections)
        if classroom and classroom.capacity is not None and classroom.capacity < combined_strength:
            raise HTTPException(422, f"COMBINED_TEACHING_CAPACITY_EXCEEDED: capacity {classroom.capacity} is below combined strength {combined_strength}")
        if laboratory and laboratory.capacity is not None and laboratory.capacity < combined_strength:
            raise HTTPException(422, f"COMBINED_TEACHING_CAPACITY_EXCEEDED: capacity {laboratory.capacity} is below combined strength {combined_strength}")
        return offerings, sections, combined_strength, classroom.capacity if classroom else laboratory.capacity if laboratory else None

    def _response(self, db: Session, group: CombinedTeachingGroup):
        members = combined_teaching_repository.members(db, group.id)
        offerings = [db.get(CourseOffering, member.course_offering_id) for member in members]
        sections = {row.section_id: db.get(Section, row.section_id) for row in offerings}
        course = db.get(Course, group.course_id)
        room = db.get(Classroom, group.preferred_classroom_id) if group.preferred_classroom_id else None
        laboratory = db.get(Laboratory, group.preferred_laboratory_id) if group.preferred_laboratory_id else None
        rows = [{"course_offering_id": row.id, "section_id": row.section_id, "section_code": sections[row.section_id].section_code, "section_strength": sections[row.section_id].student_strength, "course_code": course.course_code, "course_name": course.course_name} for row in sorted(offerings, key=lambda item: (sections[item.section_id].section_code, item.id))]
        strength = sum(row["section_strength"] for row in rows)
        capacity = room.capacity if room else laboratory.capacity if laboratory else None
        return {"id": group.id, "academic_term_id": group.academic_term_id, "group_code": group.group_code, "group_name": group.group_name, "course_id": group.course_id, "faculty_id": group.faculty_id, "preferred_classroom_id": group.preferred_classroom_id, "preferred_laboratory_id": group.preferred_laboratory_id, "is_active": group.is_active, "combined_strength": strength, "venue_capacity": capacity, "capacity_status": "OK" if capacity is not None and capacity >= strength else "EXCEEDED" if capacity is not None else "NOT_CONFIGURED", "offerings": rows, "created_at": group.created_at, "updated_at": group.updated_at}

    def create(self, db: Session, payload: CombinedTeachingGroupCreate):
        data = payload.model_dump()
        if db.scalar(select(CombinedTeachingGroup).where(CombinedTeachingGroup.academic_term_id == data["academic_term_id"], CombinedTeachingGroup.group_code == data["group_code"])):
            raise HTTPException(409, "Combined teaching group code already exists in this term")
        self._values(db, data)
        ids = data.pop("course_offering_ids"); now = datetime.now(timezone.utc)
        group = CombinedTeachingGroup(**data, created_at=now, updated_at=now); db.add(group); db.flush()
        db.add_all([CombinedTeachingGroupMember(combined_teaching_group_id=group.id, course_offering_id=value, created_at=now, updated_at=now) for value in ids])
        db.commit(); db.refresh(group); return self._response(db, group)

    def get(self, db: Session, group_id: UUID):
        group = combined_teaching_repository.get(db, group_id)
        if not group: raise HTTPException(404, "Combined teaching group not found")
        return self._response(db, group)

    def list(self, db: Session, **filters):
        groups, total = combined_teaching_repository.list(db, **filters)
        page, page_size = filters["page"], filters["page_size"]
        return {"items": [self._response(db, row) for row in groups], "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    def update(self, db: Session, group_id: UUID, payload: CombinedTeachingGroupUpdate):
        group = combined_teaching_repository.get(db, group_id)
        if not group: raise HTTPException(404, "Combined teaching group not found")
        values = {"academic_term_id": group.academic_term_id, "group_code": group.group_code, "group_name": group.group_name, "course_id": group.course_id, "faculty_id": group.faculty_id, "preferred_classroom_id": group.preferred_classroom_id, "preferred_laboratory_id": group.preferred_laboratory_id, "course_offering_ids": [row.course_offering_id for row in combined_teaching_repository.members(db, group.id)]}
        values.update(payload.model_dump(exclude_unset=True)); self._values(db, values, group.id)
        ids = values.pop("course_offering_ids"); now = datetime.now(timezone.utc)
        for key, value in values.items(): setattr(group, key, value)
        group.updated_at = now
        existing = {row.course_offering_id: row for row in combined_teaching_repository.members(db, group.id, False)}
        for row in existing.values(): row.is_active = row.course_offering_id in ids; row.updated_at = now
        for value in ids:
            if value not in existing: db.add(CombinedTeachingGroupMember(combined_teaching_group_id=group.id, course_offering_id=value, created_at=now, updated_at=now))
        db.commit(); db.refresh(group); return self._response(db, group)

    def deactivate(self, db: Session, group_id: UUID):
        group = combined_teaching_repository.get(db, group_id)
        if not group: raise HTTPException(404, "Combined teaching group not found")
        group.is_active = False; group.updated_at = datetime.now(timezone.utc); db.commit()

    def restore(self, db: Session, group_id: UUID):
        group = combined_teaching_repository.get(db, group_id)
        if not group: raise HTTPException(404, "Combined teaching group not found")
        values = {"academic_term_id": group.academic_term_id, "course_id": group.course_id, "faculty_id": group.faculty_id, "preferred_classroom_id": group.preferred_classroom_id, "preferred_laboratory_id": group.preferred_laboratory_id, "course_offering_ids": [row.course_offering_id for row in combined_teaching_repository.members(db, group.id)]}
        self._values(db, values, group.id); group.is_active = True; group.updated_at = datetime.now(timezone.utc); db.commit(); db.refresh(group); return self._response(db, group)


combined_teaching_service = CombinedTeachingService()
