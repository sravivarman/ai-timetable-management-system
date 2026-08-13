"""Academic term API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.academic_terms.schemas import AcademicTermCreate, AcademicTermPage, AcademicTermRead, AcademicTermUpdate
from app.modules.academic_terms.services import academic_term_service
from app.modules.authentication.dependencies import require_permission

router = APIRouter(prefix="/academic-terms", tags=["academic terms"])
read_terms = Depends(require_permission("academic_terms", "read"))
manage_terms = Depends(require_permission("academic_terms", "manage"))


@router.get("", response_model=AcademicTermPage, dependencies=[read_terms])
def list_terms(db: Session = Depends(get_db), search: str | None = Query(default=None, min_length=1), academic_year: str | None = None, year_number: int | None = Query(default=None, ge=1, le=4), semester_number: int | None = Query(default=None, ge=1, le=2), is_active: bool | None = None, is_current: bool | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)) -> AcademicTermPage:
    return academic_term_service.list_terms(db, search=search, academic_year=academic_year, year_number=year_number, semester_number=semester_number, is_active=is_active, is_current=is_current, page=page, page_size=page_size)


@router.get("/{academic_term_id}", response_model=AcademicTermRead, dependencies=[read_terms])
def get_term(academic_term_id: UUID, db: Session = Depends(get_db)) -> AcademicTermRead:
    return academic_term_service.get_term(db, academic_term_id)


@router.post("", response_model=AcademicTermRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_terms])
def create_term(payload: AcademicTermCreate, db: Session = Depends(get_db)) -> AcademicTermRead:
    return academic_term_service.create_term(db, payload)


@router.put("/{academic_term_id}", response_model=AcademicTermRead, dependencies=[manage_terms])
def update_term(academic_term_id: UUID, payload: AcademicTermUpdate, db: Session = Depends(get_db)) -> AcademicTermRead:
    return academic_term_service.update_term(db, academic_term_id, payload)


@router.delete("/{academic_term_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_terms])
def delete_term(academic_term_id: UUID, db: Session = Depends(get_db)) -> Response:
    academic_term_service.soft_delete_term(db, academic_term_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{academic_term_id}/restore", response_model=AcademicTermRead, dependencies=[manage_terms])
def restore_term(academic_term_id: UUID, db: Session = Depends(get_db)) -> AcademicTermRead:
    return academic_term_service.restore_term(db, academic_term_id)
