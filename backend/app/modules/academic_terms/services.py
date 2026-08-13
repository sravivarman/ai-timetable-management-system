"""Academic term management use cases."""

from datetime import date
from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm
from app.modules.academic_terms.repositories import AcademicTermRepository
from app.modules.academic_terms.schemas import AcademicTermCreate, AcademicTermPage, AcademicTermUpdate, TERM_NAMES


class AcademicTermService:
    def __init__(self) -> None:
        self.repository = AcademicTermRepository()

    def list_terms(self, db: Session, **filters) -> AcademicTermPage:
        page, page_size = filters.pop("page"), filters.pop("page_size")
        items, total = self.repository.list(db, **filters, offset=(page - 1) * page_size, limit=page_size)
        return AcademicTermPage(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

    def get_term(self, db: Session, term_id: UUID) -> AcademicTerm:
        term = self.repository.get(db, term_id)
        if term is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")
        return term

    def create_term(self, db: Session, payload: AcademicTermCreate) -> AcademicTerm:
        self._ensure_active_key_available(db, payload.academic_year, payload.year_number, payload.semester_number, payload.is_active)
        return self.repository.save(db, AcademicTerm(**payload.model_dump()))

    def update_term(self, db: Session, term_id: UUID, payload: AcademicTermUpdate) -> AcademicTerm:
        term = self.get_term(db, term_id)
        values = {field: getattr(term, field) for field in ("academic_year", "term_name", "year_number", "semester_number", "start_date", "end_date", "is_active", "is_current", "is_first_year_term")}
        values.update(payload.model_dump(exclude_unset=True))
        self._validate_values(values)
        self._ensure_active_key_available(db, values["academic_year"], values["year_number"], values["semester_number"], values["is_active"], exclude_id=term.id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(term, field, value)
        return self.repository.save(db, term)

    def soft_delete_term(self, db: Session, term_id: UUID) -> AcademicTerm:
        term = self.get_term(db, term_id)
        term.is_active, term.is_current = False, False
        return self.repository.save(db, term)

    def restore_term(self, db: Session, term_id: UUID) -> AcademicTerm:
        term = self.get_term(db, term_id)
        self._ensure_active_key_available(db, term.academic_year, term.year_number, term.semester_number, True, exclude_id=term.id)
        term.is_active = True
        return self.repository.save(db, term)

    def _validate_values(self, values: dict) -> None:
        if values["term_name"] != TERM_NAMES[(values["year_number"], values["semester_number"])]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="term_name does not match year and semester")
        if values["start_date"] >= values["end_date"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start_date must be before end_date")
        if values["is_current"] and not values["is_active"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A current term must be active")

    def _ensure_active_key_available(self, db: Session, academic_year: str, year_number: int, semester_number: int, is_active: bool, exclude_id: UUID | None = None) -> None:
        if not is_active:
            return
        existing = self.repository.get_active_by_key(db, academic_year, year_number, semester_number)
        if existing is not None and existing.id != exclude_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active academic term already exists for this year and semester")


academic_term_service = AcademicTermService()
