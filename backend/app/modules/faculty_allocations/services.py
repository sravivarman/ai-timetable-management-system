"""Allocation eligibility, integrity, and workload-preview rules."""

from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, LaboratorySessionFacultyRule, TheoryFacultyAllocation
from app.modules.faculty_allocations.repositories import AllocationRepository
from app.modules.faculty_allocations.schemas import AllocationPage, LaboratoryAllocationCreate, LaboratoryAllocationUpdate, LaboratorySessionRuleCreate, LaboratorySessionRuleUpdate, TheoryAllocationCreate, TheoryAllocationUpdate, WorkloadPreviewItem
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.faculty_allocations.workload import configured_faculty_workloads


class FacultyAllocationService:
    def __init__(self) -> None: self.repository = AllocationRepository()

    def list_items(self, db: Session, model, *, page: int, page_size: int, **filters) -> AllocationPage:
        items, total = self.repository.list(db, model, filters=filters, offset=(page - 1) * page_size, limit=page_size)
        return AllocationPage(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

    def get(self, db: Session, model, item_id: UUID):
        item = self.repository.get(db, model, item_id)
        if not item: raise HTTPException(404, "Allocation not found")
        return item

    def create_theory(self, db: Session, payload: TheoryAllocationCreate):
        self._validate_offering_and_faculty(db, payload.course_offering_id, payload.faculty_id, "THEORY")
        if db.scalar(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id == payload.course_offering_id, TheoryFacultyAllocation.is_active.is_(True))):
            raise HTTPException(409, "A theory offering already has an active faculty allocation")
        return self.repository.save(db, TheoryFacultyAllocation(**payload.model_dump()))

    def update_theory(self, db: Session, item_id: UUID, payload: TheoryAllocationUpdate):
        item = self.get(db, TheoryFacultyAllocation, item_id)
        self._validate_offering_and_faculty(db, item.course_offering_id, payload.faculty_id, "THEORY")
        item.faculty_id = payload.faculty_id
        return self.repository.save(db, item)

    def create_laboratory(self, db: Session, payload: LaboratoryAllocationCreate):
        data = payload.model_dump(); self._validate_offering_and_faculty(db, data["course_offering_id"], data["faculty_id"], "LABORATORY")
        self._validate_lab_data(db, data)
        existing = db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id == data["course_offering_id"], LaboratoryFacultyAllocation.faculty_id == data["faculty_id"], LaboratoryFacultyAllocation.is_active.is_(True)))
        if existing: raise HTTPException(409, "Faculty is already allocated to this laboratory offering")
        return self.repository.save(db, LaboratoryFacultyAllocation(**data))

    def update_laboratory(self, db: Session, item_id: UUID, payload: LaboratoryAllocationUpdate):
        item = self.get(db, LaboratoryFacultyAllocation, item_id); changes = payload.model_dump(exclude_unset=True)
        data = {column.name: getattr(item, column.name) for column in LaboratoryFacultyAllocation.__table__.columns if column.name not in {"id", "is_active", "created_at", "updated_at"}}; data.update(changes)
        self._validate_lab_data(db, data, exclude_id=item.id)
        if item.role_type == "MAIN" and data["role_type"] != "MAIN": self._ensure_not_last_main(db, item)
        for name, value in changes.items(): setattr(item, name, value)
        return self.repository.save(db, item)

    def create_rule(self, db: Session, payload: LaboratorySessionRuleCreate):
        allocation = self.get(db, LaboratoryFacultyAllocation, payload.laboratory_faculty_allocation_id)
        if not allocation.is_active: raise HTTPException(422, "Laboratory faculty allocation must be active")
        if db.scalar(select(LaboratorySessionFacultyRule).where(LaboratorySessionFacultyRule.laboratory_faculty_allocation_id == payload.laboratory_faculty_allocation_id, LaboratorySessionFacultyRule.session_number == payload.session_number)):
            raise HTTPException(409, "A rule already exists for this allocation and session")
        return self.repository.save(db, LaboratorySessionFacultyRule(**payload.model_dump()))

    def update_rule(self, db: Session, item_id: UUID, payload: LaboratorySessionRuleUpdate):
        item = self.get(db, LaboratorySessionFacultyRule, item_id)
        for name, value in payload.model_dump(exclude_unset=True).items(): setattr(item, name, value)
        return self.repository.save(db, item)

    def soft_delete(self, db: Session, model, item_id: UUID):
        item = self.get(db, model, item_id)
        if model is LaboratoryFacultyAllocation and item.role_type == "MAIN": self._ensure_not_last_main(db, item)
        item.is_active = False; return self.repository.save(db, item)

    def restore(self, db: Session, model, item_id: UUID):
        item = self.get(db, model, item_id)
        if model is TheoryFacultyAllocation:
            self._validate_offering_and_faculty(db, item.course_offering_id, item.faculty_id, "THEORY")
            conflict = db.scalar(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id == item.course_offering_id, TheoryFacultyAllocation.is_active.is_(True), TheoryFacultyAllocation.id != item.id))
            if conflict: raise HTTPException(409, "A theory offering already has an active faculty allocation")
        elif model is LaboratoryFacultyAllocation:
            self._validate_offering_and_faculty(db, item.course_offering_id, item.faculty_id, "LABORATORY")
        item.is_active = True; return self.repository.save(db, item)

    def preview(self, db: Session, *, faculty_id: UUID | None, academic_term_id: UUID | None, department_id: UUID | None) -> list[WorkloadPreviewItem]:
        results = configured_faculty_workloads(
            db,
            faculty_id=faculty_id,
            academic_term_id=academic_term_id,
            department_id=department_id,
        )
        return [WorkloadPreviewItem(faculty_id=id, weekly_workload_hours=hours) for id, hours in sorted(results.items(), key=lambda item: str(item[0]))]

    @staticmethod
    def _validate_offering_and_faculty(db: Session, offering_id: UUID, faculty_id: UUID, expected_type: str) -> None:
        offering = db.scalar(select(CourseOffering).where(CourseOffering.id == offering_id)); faculty = db.scalar(select(Faculty).where(Faculty.id == faculty_id))
        if not offering or not offering.is_active: raise HTTPException(422, "Course offering must exist and be active")
        if not faculty or not faculty.is_active: raise HTTPException(422, "Faculty must exist and be active")
        course = db.scalar(select(Course).where(Course.id == offering.course_id))
        eligible = course and (course.course_type == "LABORATORY" if expected_type == "LABORATORY" else course.course_type != "LABORATORY")
        if not eligible:
            label = "non-laboratory" if expected_type == "THEORY" else "laboratory"
            raise HTTPException(422, f"Allocation is allowed only for {label} course offerings")

    def _validate_lab_data(self, db: Session, data: dict, exclude_id: UUID | None = None) -> None:
        if data.get("required_with_main_faculty_id"):
            main = db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id == data["course_offering_id"], LaboratoryFacultyAllocation.faculty_id == data["required_with_main_faculty_id"], LaboratoryFacultyAllocation.role_type == "MAIN", LaboratoryFacultyAllocation.is_active.is_(True)))
            if not main: raise HTTPException(422, "required_with_main_faculty_id must be an active MAIN faculty allocation for this offering")
        low, high = data.get("minimum_sessions_per_week"), data.get("maximum_sessions_per_week")
        if low is not None and high is not None and high < low: raise HTTPException(422, "maximum sessions must be at least minimum sessions")

    @staticmethod
    def _ensure_not_last_main(db: Session, item: LaboratoryFacultyAllocation) -> None:
        mains = db.scalar(select(func.count()).select_from(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id == item.course_offering_id, LaboratoryFacultyAllocation.role_type == "MAIN", LaboratoryFacultyAllocation.is_active.is_(True))) or 0
        if mains <= 1: raise HTTPException(422, "A laboratory offering must retain at least one active MAIN faculty allocation")


faculty_allocation_service = FacultyAllocationService()
