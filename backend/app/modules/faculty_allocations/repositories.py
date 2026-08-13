"""Faculty allocation persistence helpers."""

from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.modules.course_offerings.models import CourseOffering
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, LaboratorySessionFacultyRule


class AllocationRepository:
    def get(self, db: Session, model, item_id: UUID):
        return db.scalar(select(model).where(model.id == item_id))

    def list(self, db: Session, model, *, filters: dict, offset: int, limit: int):
        query = select(model)
        if filters.get("academic_term_id") is not None or filters.get("department_id") is not None:
            if model is LaboratorySessionFacultyRule:
                query = query.join(LaboratoryFacultyAllocation, LaboratoryFacultyAllocation.id == model.laboratory_faculty_allocation_id).join(CourseOffering, CourseOffering.id == LaboratoryFacultyAllocation.course_offering_id)
            else:
                query = query.join(CourseOffering, CourseOffering.id == model.course_offering_id)
            if filters.get("academic_term_id") is not None:
                query = query.where(CourseOffering.academic_term_id == filters["academic_term_id"])
            if filters.get("department_id") is not None:
                query = query.join(Section, Section.id == CourseOffering.section_id).join(Program, Program.id == Section.program_id).where(Program.department_id == filters["department_id"])
        for name, value in filters.items():
            if value is not None and hasattr(model, name):
                query = query.where(getattr(model, name) == value)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        return list(db.scalars(query.order_by(model.created_at).offset(offset).limit(limit))), total

    def save(self, db: Session, item):
        db.add(item); db.commit(); db.refresh(item); return item
