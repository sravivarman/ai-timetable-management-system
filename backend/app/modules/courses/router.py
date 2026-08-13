"""Course master API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.courses.schemas import CourseCreate, CoursePage, CourseRead, CourseUpdate
from app.modules.courses.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])
read_courses = Depends(require_permission("courses", "read"))
manage_courses = Depends(require_permission("courses", "manage"))


@router.get("", response_model=CoursePage, dependencies=[read_courses], summary="List courses")
def list_courses(db: Session = Depends(get_db), search: str | None = Query(None, min_length=1, max_length=255), offering_department_id: UUID | None = None, course_type: str | None = None, elective_type: str | None = None, counts_toward_workload: bool | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> CoursePage:
    return course_service.list_courses(db, search=search, offering_department_id=offering_department_id, course_type=course_type, elective_type=elective_type, counts_toward_workload=counts_toward_workload, is_active=is_active, page=page, page_size=page_size)


@router.get("/{course_id}", response_model=CourseRead, dependencies=[read_courses])
def get_course(course_id: UUID, db: Session = Depends(get_db)) -> CourseRead:
    return course_service.get_course(db, course_id)


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_courses])
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> CourseRead:
    return course_service.create_course(db, payload)


@router.put("/{course_id}", response_model=CourseRead, dependencies=[manage_courses])
def update_course(course_id: UUID, payload: CourseUpdate, db: Session = Depends(get_db)) -> CourseRead:
    return course_service.update_course(db, course_id, payload)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_courses])
def delete_course(course_id: UUID, db: Session = Depends(get_db)) -> Response:
    course_service.soft_delete_course(db, course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{course_id}/restore", response_model=CourseRead, dependencies=[manage_courses])
def restore_course(course_id: UUID, db: Session = Depends(get_db)) -> CourseRead:
    return course_service.restore_course(db, course_id)
