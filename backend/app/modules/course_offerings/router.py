"""Course offering API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.course_offerings.schemas import CourseOfferingBulkCreate, CourseOfferingCreate, CourseOfferingPage, CourseOfferingRead, CourseOfferingUpdate
from app.modules.course_offerings.services import course_offering_service

router = APIRouter(prefix="/course-offerings", tags=["course-offerings"])
read_offerings = Depends(require_permission("course_offerings", "read"))
manage_offerings = Depends(require_permission("course_offerings", "manage"))


@router.get("", response_model=CourseOfferingPage, dependencies=[read_offerings], summary="List course offerings")
def list_offerings(db: Session = Depends(get_db), search: str | None = Query(None, min_length=1, max_length=255), course_id: UUID | None = None, section_id: UUID | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None, course_type: str | None = None, is_mandatory: bool | None = None, is_common_theory: bool | None = Query(None, deprecated=True, description="Deprecated compatibility filter; use Combined Teaching Groups."), is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> CourseOfferingPage:
    return course_offering_service.list_offerings(db, search=search, course_id=course_id, section_id=section_id, academic_term_id=academic_term_id, department_id=department_id, course_type=course_type, is_mandatory=is_mandatory, is_common_theory=is_common_theory, is_active=is_active, page=page, page_size=page_size)


@router.post("/bulk", response_model=list[CourseOfferingRead], status_code=status.HTTP_201_CREATED, dependencies=[manage_offerings])
def create_bulk(payload: CourseOfferingBulkCreate, db: Session = Depends(get_db)) -> list[CourseOfferingRead]:
    return course_offering_service.create_bulk(db, payload)


@router.get("/{course_offering_id}", response_model=CourseOfferingRead, dependencies=[read_offerings])
def get_offering(course_offering_id: UUID, db: Session = Depends(get_db)) -> CourseOfferingRead:
    return course_offering_service.get_offering(db, course_offering_id)


@router.post("", response_model=CourseOfferingRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_offerings])
def create_offering(payload: CourseOfferingCreate, db: Session = Depends(get_db)) -> CourseOfferingRead:
    return course_offering_service.create_offering(db, payload)


@router.put("/{course_offering_id}", response_model=CourseOfferingRead, dependencies=[manage_offerings])
def update_offering(course_offering_id: UUID, payload: CourseOfferingUpdate, db: Session = Depends(get_db)) -> CourseOfferingRead:
    return course_offering_service.update_offering(db, course_offering_id, payload)


@router.delete("/{course_offering_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_offerings])
def delete_offering(course_offering_id: UUID, db: Session = Depends(get_db)) -> Response:
    course_offering_service.soft_delete_offering(db, course_offering_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{course_offering_id}/restore", response_model=CourseOfferingRead, dependencies=[manage_offerings])
def restore_offering(course_offering_id: UUID, db: Session = Depends(get_db)) -> CourseOfferingRead:
    return course_offering_service.restore_offering(db, course_offering_id)
