"""Section management use cases."""

from math import ceil
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.academic_terms.models import AcademicTerm
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.sections.repositories import SectionRepository
from app.modules.sections.schemas import SectionBulkCreate, SectionCreate, SectionInput, SectionPage, SectionUpdate


class SectionService:
    def __init__(self) -> None: self.repository = SectionRepository()

    def list_sections(self, db: Session, **filters) -> SectionPage:
        page, page_size = filters.pop("page"), filters.pop("page_size")
        items, total = self.repository.list(db, **filters, offset=(page - 1) * page_size, limit=page_size)
        return SectionPage(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

    def get_section(self, db: Session, section_id: UUID) -> Section:
        section = self.repository.get(db, section_id)
        if section is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        return section

    def create_section(self, db: Session, payload: SectionCreate) -> Section:
        return self.repository.save(db, self._new_section(db, payload.program_id, payload.academic_term_id, payload))

    def bulk_create(self, db: Session, payload: SectionBulkCreate) -> list[Section]:
        names = [item.section_name for item in payload.sections]
        if len(names) != len(set(names)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Section names must be unique in a bulk request")
        sections = [self._new_section(db, payload.program_id, payload.academic_term_id, item) for item in payload.sections]
        return self.repository.save_many(db, sections)

    def update_section(self, db: Session, section_id: UUID, payload: SectionUpdate) -> Section:
        section = self.get_section(db, section_id)
        changes = payload.model_dump(exclude_unset=True)
        program_id, term_id = changes.get("program_id", section.program_id), changes.get("academic_term_id", section.academic_term_id)
        department_code = self._validate_parents(db, program_id, term_id)
        section_name = changes.get("section_name", section.section_name)
        self._ensure_unique(db, program_id, term_id, section_name, section.id)
        for field, value in changes.items(): setattr(section, field, value)
        section.section_code = f"{department_code}-{section_name}"
        return self.repository.save(db, section)

    def soft_delete(self, db: Session, section_id: UUID) -> Section:
        section = self.get_section(db, section_id); section.is_active = False
        return self.repository.save(db, section)

    def restore(self, db: Session, section_id: UUID) -> Section:
        section = self.get_section(db, section_id)
        self._validate_parents(db, section.program_id, section.academic_term_id)
        section.is_active = True
        return self.repository.save(db, section)

    def _new_section(self, db: Session, program_id: UUID, term_id: UUID, payload: SectionInput) -> Section:
        department_code = self._validate_parents(db, program_id, term_id)
        self._ensure_unique(db, program_id, term_id, payload.section_name)
        return Section(program_id=program_id, academic_term_id=term_id, section_name=payload.section_name, section_code=f"{department_code}-{payload.section_name}", student_strength=payload.student_strength, primary_classroom_id=payload.primary_classroom_id)

    def _validate_parents(self, db: Session, program_id: UUID, term_id: UUID) -> str:
        row = db.execute(select(Program, Department).join(Department, Program.department_id == Department.id).where(Program.id == program_id)).first()
        if row is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Program does not exist")
        program, department = row
        if not program.is_active: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Program is inactive")
        if not department.is_active: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Program department is inactive")
        term = db.scalar(select(AcademicTerm).where(AcademicTerm.id == term_id))
        if term is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Academic term does not exist")
        if not term.is_active: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Academic term is inactive")
        return department.department_code

    def _ensure_unique(self, db: Session, program_id: UUID, term_id: UUID, section_name: str, exclude_id: UUID | None = None) -> None:
        existing = self.repository.get_by_key(db, program_id, term_id, section_name)
        if existing is not None and existing.id != exclude_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Section name already exists for this program and academic term")


section_service = SectionService()
