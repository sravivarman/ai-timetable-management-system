from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.scheduling_slots.schemas import *
from app.modules.scheduling_slots.service import scheduling_slot_service as service
from app.modules.scheduling_slots.progress import session_counting_service


router = APIRouter(tags=["scheduling-slots"])
slot_read = Depends(require_permission("scheduling_slots", "read"))
slot_manage = Depends(require_permission("scheduling_slots", "manage"))
requirement_read = Depends(require_permission("slot_requirements", "read"))
requirement_manage = Depends(require_permission("slot_requirements", "manage"))
semester_read = Depends(require_permission("semester_requirements", "read"))
semester_manage = Depends(require_permission("semester_requirements", "manage"))


@router.post("/scheduling-slots", response_model=SchedulingSlotResponse, status_code=201, dependencies=[slot_manage])
def create_slot(payload: SchedulingSlotCreate, db: Session = Depends(get_db)):
    return {**service.slot_dict(service.create(db, payload)), "working_date_count": 0}


@router.get("/scheduling-slots", response_model=SchedulingSlotPage, dependencies=[slot_read])
def list_slots(academic_term_id: UUID | None = None, is_active: bool | None = None, search: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return service.list(db, page, page_size, academic_term_id, is_active, search)


@router.get("/scheduling-slots/{slot_id}", response_model=SchedulingSlotResponse, dependencies=[slot_read])
def get_slot(slot_id: UUID, db: Session = Depends(get_db)):
    slot = service.get(db, slot_id); dates = service.working_dates(db, slot.id)
    return {**service.slot_dict(slot), "working_date_count": len(dates)}


@router.put("/scheduling-slots/{slot_id}", response_model=SchedulingSlotResponse, dependencies=[slot_manage])
def update_slot(slot_id: UUID, payload: SchedulingSlotUpdate, db: Session = Depends(get_db)):
    slot = service.update(db, slot_id, payload); return {**service.slot_dict(slot), "working_date_count": len(service.working_dates(db, slot.id))}


@router.delete("/scheduling-slots/{slot_id}", status_code=204, dependencies=[slot_manage])
def delete_slot(slot_id: UUID, db: Session = Depends(get_db)):
    service.deactivate(db, slot_id); return Response(status_code=204)


@router.post("/scheduling-slots/{slot_id}/restore", response_model=SchedulingSlotResponse, dependencies=[slot_manage])
def restore_slot(slot_id: UUID, db: Session = Depends(get_db)):
    slot = service.restore(db, slot_id); return {**service.slot_dict(slot), "working_date_count": len(service.working_dates(db, slot.id))}


@router.get("/scheduling-slots/{slot_id}/working-dates", response_model=list[WorkingDateResponse], dependencies=[slot_read])
def working_dates(slot_id: UUID, is_active: bool | None = True, db: Session = Depends(get_db)):
    return service.working_dates(db, slot_id, is_active)


@router.post("/scheduling-slots/{slot_id}/working-dates", response_model=list[WorkingDateResponse], dependencies=[slot_manage])
def set_working_dates(slot_id: UUID, payload: WorkingDateBulkRequest, db: Session = Depends(get_db)):
    return service.set_working_dates(db, slot_id, payload.working_dates, payload.replace)


@router.delete("/scheduling-slots/{slot_id}/working-dates/{working_date_id}", status_code=204, dependencies=[slot_manage])
def delete_working_date(slot_id: UUID, working_date_id: UUID, db: Session = Depends(get_db)):
    service.delete_working_date(db, slot_id, working_date_id); return Response(status_code=204)


@router.get("/scheduling-slots/{slot_id}/completeness", response_model=RequirementCompleteness, dependencies=[requirement_read])
def completeness(slot_id: UUID, department_id: UUID | None = None, program_id: UUID | None = None, section_id: UUID | None = None, course_id: UUID | None = None, course_type: str | None = None, db: Session = Depends(get_db)):
    return service.completeness(db, slot_id, department_id=department_id, program_id=program_id, section_id=section_id, course_id=course_id, course_type=course_type)


@router.post("/slot-course-requirements", response_model=SlotRequirementResponse, status_code=201, dependencies=[requirement_manage])
def create_requirement(payload: SlotRequirementCreate, db: Session = Depends(get_db)):
    return service.create_requirement(db, payload)


@router.get("/slot-course-requirements", response_model=SlotRequirementPage, dependencies=[requirement_read])
def list_requirements(scheduling_slot_id: UUID | None = None, course_offering_id: UUID | None = None, academic_term_id: UUID | None = None, is_active: bool | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return service.list_requirements(db, page, page_size, scheduling_slot_id, course_offering_id, academic_term_id, is_active)


@router.get("/slot-course-requirements/matrix", response_model=RequirementMatrixResponse, dependencies=[requirement_read])
def matrix(academic_term_id: UUID, department_id: UUID | None = None, program_id: UUID | None = None, section_id: UUID | None = None, course_id: UUID | None = None, course_type: str | None = None, db: Session = Depends(get_db)):
    return service.matrix(db, academic_term_id, department_id=department_id, program_id=program_id, section_id=section_id, course_id=course_id, course_type=course_type)


@router.post("/slot-course-requirements/bulk", dependencies=[requirement_manage])
def bulk_requirements(payload: RequirementBulkRequest, db: Session = Depends(get_db)):
    return service.bulk(db, payload.cells)


@router.post("/slot-course-requirements/copy", dependencies=[requirement_manage])
def copy_requirements(payload: RequirementCopyRequest, db: Session = Depends(get_db)):
    return service.copy(db, payload)


@router.get("/slot-course-requirements/{requirement_id}", response_model=SlotRequirementResponse, dependencies=[requirement_read])
def get_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    return service.requirement(db, requirement_id)


@router.put("/slot-course-requirements/{requirement_id}", response_model=SlotRequirementResponse, dependencies=[requirement_manage])
def update_requirement(requirement_id: UUID, payload: SlotRequirementUpdate, db: Session = Depends(get_db)):
    return service.update_requirement(db, requirement_id, payload)


@router.delete("/slot-course-requirements/{requirement_id}", status_code=204, dependencies=[requirement_manage])
def delete_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    service.deactivate_requirement(db, requirement_id); return Response(status_code=204)


@router.post("/slot-course-requirements/{requirement_id}/restore", response_model=SlotRequirementResponse, dependencies=[requirement_manage])
def restore_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    return service.restore_requirement(db, requirement_id)


@router.post("/semester-session-requirements", response_model=SemesterRequirementResponse, status_code=201, dependencies=[semester_manage])
def create_semester_requirement(payload: SemesterRequirementCreate, db: Session = Depends(get_db)):
    return service.create_semester_requirement(db, payload)


@router.get("/semester-session-requirements", response_model=SemesterRequirementPage, dependencies=[semester_read])
def list_semester_requirements(academic_term_id: UUID | None = None, course_offering_id: UUID | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return service.list_semester_requirements(db, page, page_size, academic_term_id, course_offering_id, is_active)


@router.post("/semester-session-requirements/bulk", dependencies=[semester_manage])
def bulk_semester_requirements(payload: SemesterRequirementBulkRequest, db: Session = Depends(get_db)):
    return service.bulk_semester_requirements(db, payload.cells)


@router.get("/semester-session-requirements/{requirement_id}", response_model=SemesterRequirementResponse, dependencies=[semester_read])
def get_semester_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    return service.semester_requirement(db, requirement_id)


@router.put("/semester-session-requirements/{requirement_id}", response_model=SemesterRequirementResponse, dependencies=[semester_manage])
def update_semester_requirement(requirement_id: UUID, payload: SemesterRequirementUpdate, db: Session = Depends(get_db)):
    return service.update_semester_requirement(db, requirement_id, payload)


@router.delete("/semester-session-requirements/{requirement_id}", status_code=204, dependencies=[semester_manage])
def delete_semester_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    service.deactivate_semester_requirement(db, requirement_id); return Response(status_code=204)


@router.post("/semester-session-requirements/{requirement_id}/restore", response_model=SemesterRequirementResponse, dependencies=[semester_manage])
def restore_semester_requirement(requirement_id: UUID, db: Session = Depends(get_db)):
    return service.restore_semester_requirement(db, requirement_id)


@router.get("/semester-session-progress", response_model=list[SessionProgressRow], dependencies=[semester_read])
def semester_session_progress(academic_term_id: UUID, department_id: UUID | None = None, program_id: UUID | None = None, section_id: UUID | None = None, course_id: UUID | None = None, course_type: str | None = None, reconciliation_status: str | None = None, progress_status: str | None = None, db: Session = Depends(get_db)):
    rows = session_counting_service.progress_rows(db, academic_term_id, department_id=department_id, program_id=program_id, section_id=section_id, course_id=course_id, course_type=course_type)
    return [row for row in rows if (not reconciliation_status or row["reconciliation_status"] == reconciliation_status) and (not progress_status or row["progress_status"] == progress_status)]


@router.get("/slot-session-progress", response_model=list[SessionProgressRow], dependencies=[requirement_read])
def slot_session_progress(academic_term_id: UUID, scheduling_slot_id: UUID, department_id: UUID | None = None, program_id: UUID | None = None, section_id: UUID | None = None, course_id: UUID | None = None, course_type: str | None = None, progress_status: str | None = None, db: Session = Depends(get_db)):
    rows = session_counting_service.progress_rows(db, academic_term_id, scheduling_slot_id, department_id=department_id, program_id=program_id, section_id=section_id, course_id=course_id, course_type=course_type)
    return [row for row in rows if not progress_status or row["progress_status"] == progress_status]


@router.get("/slot-faculty-workload", dependencies=[slot_read])
def slot_faculty_workload(academic_term_id: UUID, scheduling_slot_id: UUID, faculty_id: UUID | None = None, department_id: UUID | None = None, db: Session = Depends(get_db)):
    rows = session_counting_service.slot_faculty_workload(db, academic_term_id, scheduling_slot_id)
    filtered = [row for row in rows if (not faculty_id or row["__faculty_id"] == faculty_id) and (not department_id or row["__department_id"] == department_id)]
    return [{key: value for key, value in row.items() if not key.startswith("__")} for row in filtered]
