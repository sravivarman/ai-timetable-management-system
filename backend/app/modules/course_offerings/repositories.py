"""Data access for course offerings."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.programs.models import Program
from app.modules.sections.models import Section


class CourseOfferingRepository:
    def get(self, db: Session, offering_id: UUID) -> CourseOffering | None:
        return db.scalar(select(CourseOffering).where(CourseOffering.id == offering_id))

    def get_duplicate(self, db: Session, course_id: UUID, section_id: UUID, term_id: UUID, exclude_id: UUID | None = None) -> CourseOffering | None:
        query = select(CourseOffering).where(CourseOffering.course_id == course_id, CourseOffering.section_id == section_id, CourseOffering.academic_term_id == term_id)
        if exclude_id:
            query = query.where(CourseOffering.id != exclude_id)
        return db.scalar(query)

    def list(self, db: Session, *, search: str | None, filters: dict, offset: int, limit: int) -> tuple[list[CourseOffering], int]:
        query = select(CourseOffering).join(Course, Course.id == CourseOffering.course_id).join(Section, Section.id == CourseOffering.section_id).join(Program, Program.id == Section.program_id).join(AcademicTerm, AcademicTerm.id == CourseOffering.academic_term_id)
        conditions = []
        for name in ("course_id", "section_id", "academic_term_id", "is_mandatory", "is_common_theory", "is_active"):
            if filters.get(name) is not None:
                conditions.append(getattr(CourseOffering, name) == filters[name])
        if filters.get("department_id") is not None:
            conditions.append(Program.department_id == filters["department_id"])
        if filters.get("course_type") is not None:
            conditions.append(Course.course_type == filters["course_type"])
        if search:
            term = f"%{search.strip()}%"
            conditions.append(or_(Course.course_code.ilike(term), Course.course_name.ilike(term), Section.section_code.ilike(term), CourseOffering.elective_group_name.ilike(term)))
        query = query.where(*conditions).order_by(Course.course_code, Section.section_code)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        return list(db.scalars(query.offset(offset).limit(limit))), total

    def save(self, db: Session, offering: CourseOffering) -> CourseOffering:
        db.add(offering)
        db.commit()
        db.refresh(offering)
        return offering
