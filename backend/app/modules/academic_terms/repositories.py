"""SQLAlchemy repository for academic terms."""

from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm


class AcademicTermRepository:
    def get(self, db: Session, term_id: UUID) -> AcademicTerm | None:
        return db.scalar(select(AcademicTerm).where(AcademicTerm.id == term_id))

    def get_active_by_key(self, db: Session, academic_year: str, year_number: int, semester_number: int) -> AcademicTerm | None:
        return db.scalar(select(AcademicTerm).where(AcademicTerm.academic_year == academic_year, AcademicTerm.year_number == year_number, AcademicTerm.semester_number == semester_number, AcademicTerm.is_active.is_(True)))

    def list(self, db: Session, *, search: str | None, academic_year: str | None, year_number: int | None, semester_number: int | None, is_active: bool | None, is_current: bool | None, offset: int, limit: int) -> tuple[list[AcademicTerm], int]:
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(AcademicTerm.academic_year.ilike(pattern), AcademicTerm.term_name.ilike(pattern)))
        for column, value in ((AcademicTerm.academic_year, academic_year), (AcademicTerm.year_number, year_number), (AcademicTerm.semester_number, semester_number), (AcademicTerm.is_active, is_active), (AcademicTerm.is_current, is_current)):
            if value is not None:
                filters.append(column == value)
        statement = select(AcademicTerm).where(*filters).order_by(AcademicTerm.academic_year.desc(), AcademicTerm.year_number, AcademicTerm.semester_number)
        total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        return list(db.scalars(statement.offset(offset).limit(limit))), total

    def save(self, db: Session, term: AcademicTerm) -> AcademicTerm:
        db.add(term)
        db.commit()
        db.refresh(term)
        return term
