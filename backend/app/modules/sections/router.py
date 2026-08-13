"""Section API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.sections.schemas import SectionBulkCreate, SectionCreate, SectionPage, SectionRead, SectionUpdate
from app.modules.sections.services import section_service

router = APIRouter(prefix="/sections", tags=["sections"])
read_sections = Depends(require_permission("sections", "read")); manage_sections = Depends(require_permission("sections", "manage"))

@router.get("", response_model=SectionPage, dependencies=[read_sections])
def list_sections(db: Session = Depends(get_db), search: str | None = Query(default=None, min_length=1), program_id: UUID | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None, year_number: int | None = Query(default=None, ge=1, le=4), is_active: bool | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)) -> SectionPage:
    return section_service.list_sections(db, search=search, program_id=program_id, term_id=academic_term_id, department_id=department_id, year_number=year_number, is_active=is_active, page=page, page_size=page_size)

@router.post("/bulk", response_model=list[SectionRead], status_code=status.HTTP_201_CREATED, dependencies=[manage_sections])
def bulk_create_sections(payload: SectionBulkCreate, db: Session = Depends(get_db)) -> list[SectionRead]: return section_service.bulk_create(db, payload)

@router.get("/{section_id}", response_model=SectionRead, dependencies=[read_sections])
def get_section(section_id: UUID, db: Session = Depends(get_db)) -> SectionRead: return section_service.get_section(db, section_id)

@router.post("", response_model=SectionRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_sections])
def create_section(payload: SectionCreate, db: Session = Depends(get_db)) -> SectionRead: return section_service.create_section(db, payload)

@router.put("/{section_id}", response_model=SectionRead, dependencies=[manage_sections])
def update_section(section_id: UUID, payload: SectionUpdate, db: Session = Depends(get_db)) -> SectionRead: return section_service.update_section(db, section_id, payload)

@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_sections])
def delete_section(section_id: UUID, db: Session = Depends(get_db)) -> Response: section_service.soft_delete(db, section_id); return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{section_id}/restore", response_model=SectionRead, dependencies=[manage_sections])
def restore_section(section_id: UUID, db: Session = Depends(get_db)) -> SectionRead: return section_service.restore(db, section_id)
