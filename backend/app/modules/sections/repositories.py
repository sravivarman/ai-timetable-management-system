"""SQLAlchemy repository for sections."""

from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.modules.academic_terms.models import AcademicTerm
from app.modules.programs.models import Program
from app.modules.sections.models import Section


class SectionRepository:
    def get(self, db: Session, section_id: UUID) -> Section | None:
        return db.scalar(select(Section).where(Section.id == section_id))

    def get_by_key(self, db: Session, program_id: UUID, term_id: UUID, section_name: str) -> Section | None:
        return db.scalar(select(Section).where(Section.program_id == program_id, Section.academic_term_id == term_id, Section.section_name == section_name))

    def list(self, db: Session, *, search: str | None, program_id: UUID | None, term_id: UUID | None, department_id: UUID | None, year_number: int | None, is_active: bool | None, offset: int, limit: int) -> tuple[list[Section], int]:
        statement = select(Section).join(Program, Section.program_id == Program.id).join(AcademicTerm, Section.academic_term_id == AcademicTerm.id)
        filters = []
        if search:
            pattern = f"%{search.strip()}%"; filters.append(or_(Section.section_name.ilike(pattern), Section.section_code.ilike(pattern)))
        for column, value in ((Section.program_id, program_id), (Section.academic_term_id, term_id), (Program.department_id, department_id), (AcademicTerm.year_number, year_number), (Section.is_active, is_active)):
            if value is not None: filters.append(column == value)
        statement = statement.where(*filters).order_by(Section.section_code)
        total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        return list(db.scalars(statement.offset(offset).limit(limit))), total

    def save(self, db: Session, section: Section) -> Section:
        db.add(section); db.commit(); db.refresh(section); return section

    def save_many(self, db: Session, sections: list[Section]) -> list[Section]:
        db.add_all(sections); db.commit()
        for section in sections: db.refresh(section)
        return sections
