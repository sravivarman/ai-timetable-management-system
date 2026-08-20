from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.programs.models import Program
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.scheduling_slots.models import CourseOfferingSemesterRequirement, SchedulingSlot, SchedulingSlotWorkingDate, SlotCourseRequirement
from app.modules.sections.models import Section


class SchedulingSlotService:
    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _term(self, db, term_id: UUID, active: bool = True):
        term = db.get(AcademicTerm, term_id)
        if term is None or (active and not term.is_active):
            raise HTTPException(422, "Academic term must be active")
        return term

    def get(self, db, slot_id: UUID, include_inactive: bool = True):
        slot = db.get(SchedulingSlot, slot_id)
        if slot is None or (not include_inactive and not slot.is_active):
            raise HTTPException(404, "Scheduling Slot not found")
        return slot

    def _save(self, db, value, duplicate_message: str):
        try:
            db.add(value); db.commit(); db.refresh(value); return value
        except IntegrityError as error:
            db.rollback(); raise HTTPException(409, duplicate_message) from error

    def create(self, db, data):
        self._term(db, data.academic_term_id)
        now = self._now()
        values = data.model_dump()
        values.update(slot_code=data.slot_code.strip().upper(), slot_name=data.slot_name.strip())
        slot = SchedulingSlot(**values, created_at=now, updated_at=now)
        return self._save(db, slot, "Slot code or sequence already exists for this Academic Term")

    def update(self, db, slot_id, data):
        slot = self.get(db, slot_id)
        values = data.model_dump(exclude_unset=True)
        if "slot_code" in values: values["slot_code"] = values["slot_code"].strip().upper()
        if "slot_name" in values: values["slot_name"] = values["slot_name"].strip()
        start, end = values.get("start_date", slot.start_date), values.get("end_date", slot.end_date)
        if end < start: raise HTTPException(422, "end_date must be on or after start_date")
        outside = db.scalar(select(SchedulingSlotWorkingDate.id).where(SchedulingSlotWorkingDate.scheduling_slot_id == slot.id, SchedulingSlotWorkingDate.is_active.is_(True), or_(SchedulingSlotWorkingDate.working_date < start, SchedulingSlotWorkingDate.working_date > end)))
        if outside: raise HTTPException(409, "Working dates must remain within the Slot date range")
        for field, value in values.items(): setattr(slot, field, value)
        slot.updated_at = self._now()
        return self._save(db, slot, "Slot code or sequence already exists for this Academic Term")

    def deactivate(self, db, slot_id):
        slot = self.get(db, slot_id)
        slot.is_active = False; slot.updated_at = self._now(); db.commit()

    def restore(self, db, slot_id):
        slot = self.get(db, slot_id)
        slot.is_active = True; slot.updated_at = self._now()
        return self._save(db, slot, "Slot code or sequence conflicts with an active Slot")

    def list(self, db, page, page_size, academic_term_id=None, is_active=None, search=None):
        query = select(SchedulingSlot)
        if academic_term_id: query = query.where(SchedulingSlot.academic_term_id == academic_term_id)
        if is_active is not None: query = query.where(SchedulingSlot.is_active.is_(is_active))
        if search:
            needle = f"%{search.strip()}%"
            query = query.where(or_(SchedulingSlot.slot_code.ilike(needle), SchedulingSlot.slot_name.ilike(needle)))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        slots = list(db.scalars(query.order_by(SchedulingSlot.sequence_number, SchedulingSlot.slot_code, SchedulingSlot.id).offset((page - 1) * page_size).limit(page_size)))
        counts = dict(db.execute(select(SchedulingSlotWorkingDate.scheduling_slot_id, func.count()).where(SchedulingSlotWorkingDate.scheduling_slot_id.in_([x.id for x in slots]), SchedulingSlotWorkingDate.is_active.is_(True)).group_by(SchedulingSlotWorkingDate.scheduling_slot_id)).all()) if slots else {}
        return {"items": [{**self.slot_dict(x), "working_date_count": int(counts.get(x.id, 0))} for x in slots], "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    @staticmethod
    def slot_dict(slot):
        return {field: getattr(slot, field) for field in ("id", "academic_term_id", "slot_code", "slot_name", "sequence_number", "start_date", "end_date", "is_active", "created_at", "updated_at")}

    def _validate_working_date(self, db, slot, value, exclude_id=None):
        if value < slot.start_date or value > slot.end_date:
            raise HTTPException(422, f"Working date {value.isoformat()} is outside Slot {slot.slot_code} date range")
        weekday = value.strftime("%A")
        day = db.scalar(select(WorkingDay).where(WorkingDay.day_name == weekday, WorkingDay.is_active.is_(True), WorkingDay.is_working_day.is_(True)))
        if day is None:
            raise HTTPException(422, f"{value.isoformat()} ({weekday}) is not an active institutional working day")
        conflict = db.scalar(select(SchedulingSlotWorkingDate).join(SchedulingSlot, SchedulingSlot.id == SchedulingSlotWorkingDate.scheduling_slot_id).where(SchedulingSlot.academic_term_id == slot.academic_term_id, SchedulingSlot.id != slot.id, SchedulingSlot.is_active.is_(True), SchedulingSlotWorkingDate.working_date == value, SchedulingSlotWorkingDate.is_active.is_(True)))
        if conflict and conflict.id != exclude_id:
            other = db.get(SchedulingSlot, conflict.scheduling_slot_id)
            raise HTTPException(409, f"Working date {value.isoformat()} already belongs to active Scheduling Slot {other.slot_code}")
        return day

    def set_working_dates(self, db, slot_id, values, replace=False):
        slot = self.get(db, slot_id, include_inactive=False)
        unique = sorted(set(values))
        for value in unique: self._validate_working_date(db, slot, value)
        existing = {row.working_date: row for row in db.scalars(select(SchedulingSlotWorkingDate).where(SchedulingSlotWorkingDate.scheduling_slot_id == slot.id))}
        now = self._now()
        if replace:
            for value, row in existing.items():
                if row.is_active and value not in unique: row.is_active = False; row.updated_at = now
        for value in unique:
            row = existing.get(value)
            if row: row.is_active = True; row.updated_at = now
            else: db.add(SchedulingSlotWorkingDate(scheduling_slot_id=slot.id, working_date=value, is_active=True, created_at=now, updated_at=now))
        db.commit()
        return self.working_dates(db, slot.id)

    def working_dates(self, db, slot_id, is_active=True):
        self.get(db, slot_id)
        query = select(SchedulingSlotWorkingDate).where(SchedulingSlotWorkingDate.scheduling_slot_id == slot_id)
        if is_active is not None: query = query.where(SchedulingSlotWorkingDate.is_active.is_(is_active))
        return [{**{field: getattr(row, field) for field in ("id", "scheduling_slot_id", "working_date", "is_active", "created_at", "updated_at")}, "day_name": row.working_date.strftime("%A")} for row in db.scalars(query.order_by(SchedulingSlotWorkingDate.working_date, SchedulingSlotWorkingDate.id))]

    def delete_working_date(self, db, slot_id, working_date_id):
        slot = self.get(db, slot_id)
        row = db.get(SchedulingSlotWorkingDate, working_date_id)
        if row is None or row.scheduling_slot_id != slot.id: raise HTTPException(404, "Slot Working Date not found")
        row.is_active = False; row.updated_at = self._now(); db.commit()

    def _requirement_parents(self, db, slot_id, offering_id):
        slot = self.get(db, slot_id, include_inactive=False)
        offering = db.get(CourseOffering, offering_id)
        if offering is None or not offering.is_active: raise HTTPException(422, "Course Offering must be active")
        if offering.academic_term_id != slot.academic_term_id: raise HTTPException(422, "Course Offering Academic Term does not match the Scheduling Slot")
        return slot, offering

    def _semester_parent(self, db, term_id, offering_id):
        self._term(db, term_id, active=False)
        offering = db.get(CourseOffering, offering_id)
        if offering is None or not offering.is_active:
            raise HTTPException(422, "Course Offering must be active")
        if offering.academic_term_id != term_id:
            raise HTTPException(422, "Course Offering Academic Term does not match")
        return offering

    @staticmethod
    def reconcile(required, allocated):
        if required is None:
            return {"semester_required": None, "allocated_to_slots": allocated, "remaining_to_allocate": None, "over_allocated": 0, "reconciliation_status": "NOT_CONFIGURED"}
        if allocated < required:
            return {"semester_required": required, "allocated_to_slots": allocated, "remaining_to_allocate": required - allocated, "over_allocated": 0, "reconciliation_status": "UNDER_ALLOCATED"}
        if allocated > required:
            return {"semester_required": required, "allocated_to_slots": allocated, "remaining_to_allocate": 0, "over_allocated": allocated - required, "reconciliation_status": "OVER_ALLOCATED"}
        return {"semester_required": required, "allocated_to_slots": allocated, "remaining_to_allocate": 0, "over_allocated": 0, "reconciliation_status": "FULLY_ALLOCATED"}

    def requirement(self, db, requirement_id):
        value = db.get(SlotCourseRequirement, requirement_id)
        if value is None: raise HTTPException(404, "Slot Course Requirement not found")
        return value

    def create_requirement(self, db, data):
        self._requirement_parents(db, data.scheduling_slot_id, data.course_offering_id)
        existing = db.scalar(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == data.scheduling_slot_id, SlotCourseRequirement.course_offering_id == data.course_offering_id))
        if existing:
            if existing.is_active: raise HTTPException(409, "Slot Course Requirement already exists")
            existing.sessions_required = data.sessions_required; existing.is_active = True; existing.updated_at = self._now()
            return self._save(db, existing, "Slot Course Requirement already exists")
        now = self._now()
        return self._save(db, SlotCourseRequirement(**data.model_dump(), created_at=now, updated_at=now), "Slot Course Requirement already exists")

    def update_requirement(self, db, requirement_id, data):
        value = self.requirement(db, requirement_id)
        if data.sessions_required is not None: value.sessions_required = data.sessions_required
        value.updated_at = self._now(); return self._save(db, value, "Slot Course Requirement already exists")

    def deactivate_requirement(self, db, requirement_id):
        value = self.requirement(db, requirement_id); value.is_active = False; value.updated_at = self._now(); db.commit()

    def restore_requirement(self, db, requirement_id):
        value = self.requirement(db, requirement_id); self._requirement_parents(db, value.scheduling_slot_id, value.course_offering_id); value.is_active = True; value.updated_at = self._now(); return self._save(db, value, "Active Slot Course Requirement already exists")

    def list_requirements(self, db, page, page_size, scheduling_slot_id=None, course_offering_id=None, academic_term_id=None, is_active=None):
        query = select(SlotCourseRequirement).join(SchedulingSlot)
        if scheduling_slot_id: query = query.where(SlotCourseRequirement.scheduling_slot_id == scheduling_slot_id)
        if course_offering_id: query = query.where(SlotCourseRequirement.course_offering_id == course_offering_id)
        if academic_term_id: query = query.where(SchedulingSlot.academic_term_id == academic_term_id)
        if is_active is not None: query = query.where(SlotCourseRequirement.is_active.is_(is_active))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        items = list(db.scalars(query.order_by(SchedulingSlot.sequence_number, SlotCourseRequirement.course_offering_id, SlotCourseRequirement.id).offset((page - 1) * page_size).limit(page_size)))
        return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    def _offerings_query(self, term_id, department_id=None, program_id=None, section_id=None, course_id=None, course_type=None):
        query = select(CourseOffering, Course, Section).join(Course, Course.id == CourseOffering.course_id).join(Section, Section.id == CourseOffering.section_id).join(Program, Program.id == Section.program_id).where(CourseOffering.academic_term_id == term_id, CourseOffering.is_active.is_(True), Course.is_active.is_(True), Section.is_active.is_(True), Program.is_active.is_(True))
        if department_id: query = query.where(Program.department_id == department_id)
        if program_id: query = query.where(Program.id == program_id)
        if section_id: query = query.where(Section.id == section_id)
        if course_id: query = query.where(Course.id == course_id)
        if course_type: query = query.where(Course.course_type == course_type)
        return query.order_by(Section.section_code, Course.course_code, CourseOffering.id)

    def completeness(self, db, slot_id, **filters):
        slot = self.get(db, slot_id)
        offerings = list(db.execute(self._offerings_query(slot.academic_term_id, **filters)).all())
        ids = {row[0].id for row in offerings}
        requirements = {row.course_offering_id: row for row in db.scalars(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == slot.id, SlotCourseRequirement.course_offering_id.in_(ids), SlotCourseRequirement.is_active.is_(True)))} if ids else {}
        zero = sum(row.sessions_required == 0 for row in requirements.values()); positive = sum(row.sessions_required > 0 for row in requirements.values()); missing = len(ids) - len(requirements)
        return {"scheduling_slot_id": slot.id, "slot_code": slot.slot_code, "total_active_offerings": len(ids), "configured_positive": positive, "configured_zero": zero, "missing": missing, "invalid": 0, "is_complete": missing == 0}

    def matrix(self, db, term_id, **filters):
        self._term(db, term_id, active=False)
        slots = list(db.scalars(select(SchedulingSlot).where(SchedulingSlot.academic_term_id == term_id, SchedulingSlot.is_active.is_(True)).order_by(SchedulingSlot.sequence_number, SchedulingSlot.slot_code, SchedulingSlot.id)))
        counts = dict(db.execute(select(SchedulingSlotWorkingDate.scheduling_slot_id, func.count()).where(SchedulingSlotWorkingDate.scheduling_slot_id.in_([x.id for x in slots]), SchedulingSlotWorkingDate.is_active.is_(True)).group_by(SchedulingSlotWorkingDate.scheduling_slot_id)).all()) if slots else {}
        offerings = list(db.execute(self._offerings_query(term_id, **filters)).all())
        offering_ids = {row[0].id for row in offerings}; slot_ids = {x.id for x in slots}
        requirements = {(row.scheduling_slot_id, row.course_offering_id): row for row in db.scalars(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id.in_(slot_ids), SlotCourseRequirement.course_offering_id.in_(offering_ids), SlotCourseRequirement.is_active.is_(True)))} if slot_ids and offering_ids else {}
        semester = {row.course_offering_id: row for row in db.scalars(select(CourseOfferingSemesterRequirement).where(CourseOfferingSemesterRequirement.course_offering_id.in_(offering_ids), CourseOfferingSemesterRequirement.is_active.is_(True)))} if offering_ids else {}
        rows = []
        for offering, course, section in offerings:
            cells = []
            for slot in slots:
                requirement = requirements.get((slot.id, offering.id)); sessions = requirement.sessions_required if requirement else None
                cells.append({"scheduling_slot_id": slot.id, "requirement_id": requirement.id if requirement else None, "sessions_required": sessions, "status": "MISSING" if requirement is None else "CONFIGURED_ZERO" if sessions == 0 else "CONFIGURED", "updated_at": requirement.updated_at if requirement else None})
            semester_row = semester.get(offering.id); allocated = sum(cell["sessions_required"] or 0 for cell in cells if cell["status"] != "MISSING")
            rows.append({"course_offering_id": offering.id, "section_id": section.id, "course_code": course.course_code, "course_name": course.course_name, "course_type": course.course_type, "section_code": section.section_code, "section_name": section.section_name, "semester_requirement_id": semester_row.id if semester_row else None, **self.reconcile(semester_row.total_sessions_required if semester_row else None, allocated), "cells": cells})
        return {"slots": [{**self.slot_dict(slot), "working_date_count": int(counts.get(slot.id, 0))} for slot in slots], "rows": rows, "completeness": [self.completeness(db, slot.id, **filters) for slot in slots]}

    def bulk(self, db, cells):
        seen = set(); errors = []; prepared = []
        for index, cell in enumerate(cells):
            key = (cell.scheduling_slot_id, cell.course_offering_id)
            if key in seen: errors.append({"index": index, "message": "Duplicate Slot/Course Offering in request"}); continue
            seen.add(key)
            try:
                self._requirement_parents(db, *key)
                current = db.scalar(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == key[0], SlotCourseRequirement.course_offering_id == key[1]))
                if cell.expected_updated_at and current and current.updated_at != cell.expected_updated_at: raise HTTPException(409, "Requirement changed since it was loaded")
                prepared.append((cell, current))
            except HTTPException as error: errors.append({"index": index, "message": str(error.detail)})
        if errors: raise HTTPException(422, {"message": "Slot requirement batch is invalid", "errors": errors})
        now = self._now(); inserted = updated = cleared = 0
        try:
            for cell, current in prepared:
                if cell.clear:
                    if current and current.is_active: current.is_active = False; current.updated_at = now; cleared += 1
                elif current:
                    current.sessions_required = cell.sessions_required; current.is_active = True; current.updated_at = now; updated += 1
                else:
                    db.add(SlotCourseRequirement(scheduling_slot_id=cell.scheduling_slot_id, course_offering_id=cell.course_offering_id, sessions_required=cell.sessions_required, created_at=now, updated_at=now)); inserted += 1
            db.commit()
        except Exception:
            db.rollback(); raise
        offering_ids = {cell.course_offering_id for cell, _ in prepared if not cell.clear}
        warnings = []
        if offering_ids:
            semester = {row.course_offering_id: row.total_sessions_required for row in db.scalars(select(CourseOfferingSemesterRequirement).where(CourseOfferingSemesterRequirement.course_offering_id.in_(offering_ids), CourseOfferingSemesterRequirement.is_active.is_(True)))}
            allocated = dict(db.execute(select(SlotCourseRequirement.course_offering_id, func.sum(SlotCourseRequirement.sessions_required)).join(SchedulingSlot).where(SlotCourseRequirement.course_offering_id.in_(offering_ids), SlotCourseRequirement.is_active.is_(True), SchedulingSlot.is_active.is_(True)).group_by(SlotCourseRequirement.course_offering_id)).all())
            for offering_id, required in semester.items():
                over = int(allocated.get(offering_id, 0) or 0) - required
                if over > 0: warnings.append({"course_offering_id": str(offering_id), "code": "SEMESTER_OVER_ALLOCATED", "message": f"Slot allocation exceeds semester requirement by {over} session{'s' if over != 1 else ''}."})
        return {"inserted": inserted, "updated": updated, "cleared": cleared, "warnings": warnings}

    def semester_requirement(self, db, requirement_id):
        row = db.get(CourseOfferingSemesterRequirement, requirement_id)
        if row is None: raise HTTPException(404, "Semester Session Requirement not found")
        return row

    def list_semester_requirements(self, db, page, page_size, academic_term_id=None, course_offering_id=None, is_active=None):
        query = select(CourseOfferingSemesterRequirement)
        if academic_term_id: query = query.where(CourseOfferingSemesterRequirement.academic_term_id == academic_term_id)
        if course_offering_id: query = query.where(CourseOfferingSemesterRequirement.course_offering_id == course_offering_id)
        if is_active is not None: query = query.where(CourseOfferingSemesterRequirement.is_active.is_(is_active))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        items = list(db.scalars(query.order_by(CourseOfferingSemesterRequirement.academic_term_id, CourseOfferingSemesterRequirement.course_offering_id, CourseOfferingSemesterRequirement.id).offset((page - 1) * page_size).limit(page_size)))
        return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    def create_semester_requirement(self, db, data):
        self._semester_parent(db, data.academic_term_id, data.course_offering_id)
        existing = db.scalar(select(CourseOfferingSemesterRequirement).where(CourseOfferingSemesterRequirement.course_offering_id == data.course_offering_id))
        if existing and existing.is_active: raise HTTPException(409, "Semester Session Requirement already exists")
        now = self._now()
        if existing:
            existing.academic_term_id = data.academic_term_id; existing.total_sessions_required = data.total_sessions_required; existing.is_active = True; existing.updated_at = now
            return self._save(db, existing, "Semester Session Requirement already exists")
        return self._save(db, CourseOfferingSemesterRequirement(**data.model_dump(), created_at=now, updated_at=now), "Semester Session Requirement already exists")

    def update_semester_requirement(self, db, requirement_id, data):
        row = self.semester_requirement(db, requirement_id); row.total_sessions_required = data.total_sessions_required; row.updated_at = self._now()
        return self._save(db, row, "Semester Session Requirement already exists")

    def deactivate_semester_requirement(self, db, requirement_id):
        row = self.semester_requirement(db, requirement_id); row.is_active = False; row.updated_at = self._now(); db.commit()

    def restore_semester_requirement(self, db, requirement_id):
        row = self.semester_requirement(db, requirement_id); self._semester_parent(db, row.academic_term_id, row.course_offering_id); row.is_active = True; row.updated_at = self._now()
        return self._save(db, row, "Active Semester Session Requirement already exists")

    def bulk_semester_requirements(self, db, cells):
        seen = set(); prepared = []; errors = []
        for index, cell in enumerate(cells):
            if cell.course_offering_id in seen:
                errors.append({"index": index, "message": "Duplicate Course Offering in request"}); continue
            seen.add(cell.course_offering_id)
            try:
                self._semester_parent(db, cell.academic_term_id, cell.course_offering_id)
                current = db.scalar(select(CourseOfferingSemesterRequirement).where(CourseOfferingSemesterRequirement.course_offering_id == cell.course_offering_id))
                if cell.expected_updated_at and current and current.updated_at != cell.expected_updated_at: raise HTTPException(409, "Semester requirement changed since it was loaded")
                prepared.append((cell, current))
            except HTTPException as error: errors.append({"index": index, "message": str(error.detail)})
        if errors: raise HTTPException(422, {"message": "Semester requirement batch is invalid", "errors": errors})
        now = self._now(); inserted = updated = cleared = 0
        try:
            for cell, current in prepared:
                if cell.clear:
                    if current and current.is_active: current.is_active = False; current.updated_at = now; cleared += 1
                elif current:
                    current.academic_term_id = cell.academic_term_id; current.total_sessions_required = cell.total_sessions_required; current.is_active = True; current.updated_at = now; updated += 1
                else:
                    db.add(CourseOfferingSemesterRequirement(academic_term_id=cell.academic_term_id, course_offering_id=cell.course_offering_id, total_sessions_required=cell.total_sessions_required, created_at=now, updated_at=now)); inserted += 1
            db.commit()
        except Exception:
            db.rollback(); raise
        return {"inserted": inserted, "updated": updated, "cleared": cleared}

    def copy(self, db, request):
        source = self.get(db, request.source_slot_id, include_inactive=False); target = self.get(db, request.target_slot_id, include_inactive=False)
        if source.academic_term_id != target.academic_term_id: raise HTTPException(422, "Source and target Slots must belong to the same Academic Term")
        query = select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == source.id, SlotCourseRequirement.is_active.is_(True))
        if request.course_offering_ids: query = query.where(SlotCourseRequirement.course_offering_id.in_(request.course_offering_ids))
        cells = []
        for row in db.scalars(query):
            existing = db.scalar(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == target.id, SlotCourseRequirement.course_offering_id == row.course_offering_id, SlotCourseRequirement.is_active.is_(True)))
            if existing and not request.overwrite: raise HTTPException(409, "Target Slot already contains one or more selected requirements")
            cells.append(type("Cell", (), {"scheduling_slot_id": target.id, "course_offering_id": row.course_offering_id, "sessions_required": row.sessions_required, "clear": False, "expected_updated_at": None})())
        return self.bulk(db, cells) if cells else {"inserted": 0, "updated": 0, "cleared": 0}


scheduling_slot_service = SchedulingSlotService()
