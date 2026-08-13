"""Department API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.departments.schemas import DepartmentCreate, DepartmentPage, DepartmentRead, DepartmentUpdate
from app.modules.departments.services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])
view_departments = Depends(require_permission("departments", "view"))
manage_departments = Depends(require_permission("departments", "manage"))


@router.get("", response_model=DepartmentPage, dependencies=[view_departments], summary="List departments")
def list_departments(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> DepartmentPage:
    """List departments with optional search and pagination."""
    return department_service.list_departments(
        db,
        search=search,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )


@router.get("/{department_id}", response_model=DepartmentRead, dependencies=[view_departments])
def get_department(department_id: UUID, db: Session = Depends(get_db)) -> DepartmentRead:
    return department_service.get_department(db, department_id)


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_departments])
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)) -> DepartmentRead:
    return department_service.create_department(db, payload)


@router.put("/{department_id}", response_model=DepartmentRead, dependencies=[manage_departments])
def update_department(department_id: UUID, payload: DepartmentUpdate, db: Session = Depends(get_db)) -> DepartmentRead:
    return department_service.update_department(db, department_id, payload)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_departments])
def delete_department(department_id: UUID, db: Session = Depends(get_db)) -> Response:
    """Soft-delete a department by marking it inactive."""
    department_service.soft_delete_department(db, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{department_id}/restore", response_model=DepartmentRead, dependencies=[manage_departments])
def restore_department(department_id: UUID, db: Session = Depends(get_db)) -> DepartmentRead:
    return department_service.restore_department(db, department_id)
