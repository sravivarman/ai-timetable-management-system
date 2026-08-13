"""Faculty allocation API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, LaboratorySessionFacultyRule, TheoryFacultyAllocation
from app.modules.faculty_allocations.schemas import AllocationPage, LaboratoryAllocationCreate, LaboratoryAllocationRead, LaboratoryAllocationUpdate, LaboratorySessionRuleCreate, LaboratorySessionRuleRead, LaboratorySessionRuleUpdate, TheoryAllocationCreate, TheoryAllocationRead, TheoryAllocationUpdate, WorkloadPreviewItem
from app.modules.faculty_allocations.services import faculty_allocation_service as service

router = APIRouter(prefix="/faculty-allocations", tags=["faculty-allocations"])
read = Depends(require_permission("faculty_allocations", "read")); manage = Depends(require_permission("faculty_allocations", "manage"))

def listing(model, db, course_offering_id=None, faculty_id=None, role_type=None, academic_term_id=None, department_id=None, is_active=True, page=1, page_size=20):
    return service.list_items(db, model, course_offering_id=course_offering_id, faculty_id=faculty_id, role_type=role_type, academic_term_id=academic_term_id, department_id=department_id, is_active=is_active, page=page, page_size=page_size)

@router.get("/workload-preview", response_model=list[WorkloadPreviewItem], dependencies=[read])
def workload_preview(db: Session = Depends(get_db), faculty_id: UUID | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None): return service.preview(db, faculty_id=faculty_id, academic_term_id=academic_term_id, department_id=department_id)

@router.get("/theory", response_model=AllocationPage, dependencies=[read])
def list_theory(db: Session = Depends(get_db), course_offering_id: UUID | None = None, faculty_id: UUID | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)): return listing(TheoryFacultyAllocation, db, course_offering_id, faculty_id, academic_term_id=academic_term_id, department_id=department_id, is_active=is_active, page=page, page_size=page_size)
@router.post("/theory", response_model=TheoryAllocationRead, status_code=201, dependencies=[manage])
def create_theory(payload: TheoryAllocationCreate, db: Session = Depends(get_db)): return service.create_theory(db, payload)
@router.get("/theory/{allocation_id}", response_model=TheoryAllocationRead, dependencies=[read])
def get_theory(allocation_id: UUID, db: Session = Depends(get_db)): return service.get(db, TheoryFacultyAllocation, allocation_id)
@router.put("/theory/{allocation_id}", response_model=TheoryAllocationRead, dependencies=[manage])
def update_theory(allocation_id: UUID, payload: TheoryAllocationUpdate, db: Session = Depends(get_db)): return service.update_theory(db, allocation_id, payload)
@router.delete("/theory/{allocation_id}", status_code=204, dependencies=[manage])
def delete_theory(allocation_id: UUID, db: Session = Depends(get_db)): service.soft_delete(db, TheoryFacultyAllocation, allocation_id); return Response(status_code=204)
@router.post("/theory/{allocation_id}/restore", response_model=TheoryAllocationRead, dependencies=[manage])
def restore_theory(allocation_id: UUID, db: Session = Depends(get_db)): return service.restore(db, TheoryFacultyAllocation, allocation_id)

@router.get("/laboratory", response_model=AllocationPage, dependencies=[read])
def list_laboratory(db: Session = Depends(get_db), course_offering_id: UUID | None = None, faculty_id: UUID | None = None, role_type: str | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)): return listing(LaboratoryFacultyAllocation, db, course_offering_id, faculty_id, role_type, academic_term_id, department_id, is_active, page, page_size)
@router.post("/laboratory", response_model=LaboratoryAllocationRead, status_code=201, dependencies=[manage])
def create_laboratory(payload: LaboratoryAllocationCreate, db: Session = Depends(get_db)): return service.create_laboratory(db, payload)
@router.get("/laboratory/{allocation_id}", response_model=LaboratoryAllocationRead, dependencies=[read])
def get_laboratory(allocation_id: UUID, db: Session = Depends(get_db)): return service.get(db, LaboratoryFacultyAllocation, allocation_id)
@router.put("/laboratory/{allocation_id}", response_model=LaboratoryAllocationRead, dependencies=[manage])
def update_laboratory(allocation_id: UUID, payload: LaboratoryAllocationUpdate, db: Session = Depends(get_db)): return service.update_laboratory(db, allocation_id, payload)
@router.delete("/laboratory/{allocation_id}", status_code=204, dependencies=[manage])
def delete_laboratory(allocation_id: UUID, db: Session = Depends(get_db)): service.soft_delete(db, LaboratoryFacultyAllocation, allocation_id); return Response(status_code=204)
@router.post("/laboratory/{allocation_id}/restore", response_model=LaboratoryAllocationRead, dependencies=[manage])
def restore_laboratory(allocation_id: UUID, db: Session = Depends(get_db)): return service.restore(db, LaboratoryFacultyAllocation, allocation_id)

@router.get("/laboratory-session-rules", response_model=AllocationPage, dependencies=[read])
def list_rules(db: Session = Depends(get_db), laboratory_faculty_allocation_id: UUID | None = None, academic_term_id: UUID | None = None, department_id: UUID | None = None, is_active: bool | None = True, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)): return service.list_items(db, LaboratorySessionFacultyRule, laboratory_faculty_allocation_id=laboratory_faculty_allocation_id, academic_term_id=academic_term_id, department_id=department_id, is_active=is_active, page=page, page_size=page_size)
@router.post("/laboratory-session-rules", response_model=LaboratorySessionRuleRead, status_code=201, dependencies=[manage])
def create_rule(payload: LaboratorySessionRuleCreate, db: Session = Depends(get_db)): return service.create_rule(db, payload)
@router.put("/laboratory-session-rules/{rule_id}", response_model=LaboratorySessionRuleRead, dependencies=[manage])
def update_rule(rule_id: UUID, payload: LaboratorySessionRuleUpdate, db: Session = Depends(get_db)): return service.update_rule(db, rule_id, payload)
@router.delete("/laboratory-session-rules/{rule_id}", status_code=204, dependencies=[manage])
def delete_rule(rule_id: UUID, db: Session = Depends(get_db)): service.soft_delete(db, LaboratorySessionFacultyRule, rule_id); return Response(status_code=204)
