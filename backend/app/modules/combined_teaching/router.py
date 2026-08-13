"""Combined teaching group API."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from .schemas import CombinedTeachingGroupCreate, CombinedTeachingGroupPage, CombinedTeachingGroupResponse, CombinedTeachingGroupUpdate
from .service import combined_teaching_service

router = APIRouter(prefix="/combined-teaching-groups", tags=["Combined Teaching Groups"])
read = Depends(require_permission("combined_teaching_groups", "read"))
manage = Depends(require_permission("combined_teaching_groups", "manage"))


@router.get("", response_model=CombinedTeachingGroupPage, dependencies=[read])
def list_groups(db: Session = Depends(get_db), search: str | None = None, academic_term_id: UUID | None = None, course_id: UUID | None = None, faculty_id: UUID | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return combined_teaching_service.list(db, search=search, academic_term_id=academic_term_id, course_id=course_id, faculty_id=faculty_id, is_active=is_active, page=page, page_size=page_size)


@router.get("/{group_id}", response_model=CombinedTeachingGroupResponse, dependencies=[read])
def get_group(group_id: UUID, db: Session = Depends(get_db)): return combined_teaching_service.get(db, group_id)


@router.post("", response_model=CombinedTeachingGroupResponse, status_code=status.HTTP_201_CREATED, dependencies=[manage])
def create_group(payload: CombinedTeachingGroupCreate, db: Session = Depends(get_db)): return combined_teaching_service.create(db, payload)


@router.put("/{group_id}", response_model=CombinedTeachingGroupResponse, dependencies=[manage])
def update_group(group_id: UUID, payload: CombinedTeachingGroupUpdate, db: Session = Depends(get_db)): return combined_teaching_service.update(db, group_id, payload)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage])
def delete_group(group_id: UUID, db: Session = Depends(get_db)): combined_teaching_service.deactivate(db, group_id); return Response(status_code=204)


@router.post("/{group_id}/restore", response_model=CombinedTeachingGroupResponse, dependencies=[manage])
def restore_group(group_id: UUID, db: Session = Depends(get_db)): return combined_teaching_service.restore(db, group_id)
