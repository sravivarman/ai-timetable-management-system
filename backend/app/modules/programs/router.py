"""Program API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.programs.schemas import ProgramCreate, ProgramPage, ProgramRead, ProgramUpdate
from app.modules.programs.services import program_service

router = APIRouter(prefix="/programs", tags=["programs"])
read_programs = Depends(require_permission("programs", "read"))
manage_programs = Depends(require_permission("programs", "manage"))


@router.get("", response_model=ProgramPage, dependencies=[read_programs], summary="List programs")
def list_programs(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    department_id: UUID | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProgramPage:
    """List programs with optional code/name search and department filtering."""
    return program_service.list_programs(
        db,
        search=search,
        department_id=department_id,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )


@router.get("/{program_id}", response_model=ProgramRead, dependencies=[read_programs])
def get_program(program_id: UUID, db: Session = Depends(get_db)) -> ProgramRead:
    return program_service.get_program(db, program_id)


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_programs])
def create_program(payload: ProgramCreate, db: Session = Depends(get_db)) -> ProgramRead:
    return program_service.create_program(db, payload)


@router.put("/{program_id}", response_model=ProgramRead, dependencies=[manage_programs])
def update_program(program_id: UUID, payload: ProgramUpdate, db: Session = Depends(get_db)) -> ProgramRead:
    return program_service.update_program(db, program_id, payload)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_programs])
def delete_program(program_id: UUID, db: Session = Depends(get_db)) -> Response:
    """Soft-delete a program by marking it inactive."""
    program_service.soft_delete_program(db, program_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{program_id}/restore", response_model=ProgramRead, dependencies=[manage_programs])
def restore_program(program_id: UUID, db: Session = Depends(get_db)) -> ProgramRead:
    return program_service.restore_program(db, program_id)
