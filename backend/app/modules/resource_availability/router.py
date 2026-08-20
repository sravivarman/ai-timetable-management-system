from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.resource_availability.registry import RESOURCE_REGISTRY, registration
from app.modules.resource_availability.models import ResourceDateException
from app.modules.resource_availability.schemas import ResourceAvailabilityProfileResponse, ResourceAvailabilityProfileUpdate, ResourceAvailabilitySlotCreate, ResourceAvailabilitySlotResponse, ResourceAvailabilitySlotUpdate, ResourceDateExceptionCreate, ResourceDateExceptionResponse
from app.modules.resource_availability.service import availability_service as service

router=APIRouter(prefix="/resource-availability",tags=["resource availability"])


def authorize(user:User,resource_type:str,action:str):
    kind=service.normalize_type(resource_type);required=registration(kind).manage_permission if action=="manage" else registration(kind).read_permission;granted={(permission.resource,permission.action) for role in user.roles for permission in role.permissions}
    if required not in granted:raise HTTPException(403,"Insufficient permissions")
    return kind


@router.get("/resource-types")
def resource_types(user:User=Depends(get_current_user)):
    granted={(permission.resource,permission.action) for role in user.roles for permission in role.permissions}
    return [{"resource_type":item.resource_type,"concrete_type":item.concrete_type,"endpoint":item.endpoint,"code_field":item.code_field,"name_field":item.name_field,"can_read":item.read_permission in granted,"can_manage":item.manage_permission in granted} for item in RESOURCE_REGISTRY.values() if item.read_permission in granted]


@router.get("/profiles")
def profiles(resource_type:str,resource_id:UUID|None=None,academic_term_id:UUID|None=None,is_active:bool|None=True,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    authorize(user,resource_type,"read");return service.list_profiles(db,page,page_size,resource_type,resource_id,academic_term_id,is_active)


@router.put("/{resource_type}/{resource_id}/{academic_term_id}",response_model=ResourceAvailabilityProfileResponse)
def set_mode(resource_type:str,resource_id:UUID,academic_term_id:UUID,payload:ResourceAvailabilityProfileUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    authorize(user,resource_type,"manage");return service.set_mode(db,resource_type,resource_id,academic_term_id,payload.availability_mode)


@router.get("/slots")
def slots(resource_type:str,resource_id:UUID|None=None,academic_term_id:UUID|None=None,working_day_id:UUID|None=None,period_number:int|None=Query(None,ge=1,le=7),availability_type:str|None=None,is_active:bool|None=True,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    authorize(user,resource_type,"read");return service.list_slots(db,page,page_size,resource_type=resource_type,resource_id=resource_id,academic_term_id=academic_term_id,working_day_id=working_day_id,period_number=period_number,availability_type=availability_type,is_active=is_active)


@router.post("/slots",response_model=ResourceAvailabilitySlotResponse,status_code=201)
def create_slot(payload:ResourceAvailabilitySlotCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    authorize(user,payload.resource_type,"manage");return service.create_slot(db,payload)


@router.put("/slots/{slot_id}",response_model=ResourceAvailabilitySlotResponse)
def update_slot(slot_id:UUID,payload:ResourceAvailabilitySlotUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    slot=service.get_slot(db,slot_id);authorize(user,slot.resource_type,"manage");return service.update_slot(db,slot_id,payload)


@router.delete("/slots/{slot_id}",status_code=204)
def delete_slot(slot_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    slot=service.get_slot(db,slot_id);authorize(user,slot.resource_type,"manage");service.delete_slot(db,slot_id);return Response(status_code=204)


@router.post("/slots/{slot_id}/restore",response_model=ResourceAvailabilitySlotResponse)
def restore_slot(slot_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    slot=service.get_slot(db,slot_id);authorize(user,slot.resource_type,"manage");return service.restore_slot(db,slot_id)


@router.get("/date-exceptions", response_model=list[ResourceDateExceptionResponse])
def date_exceptions(resource_type: str, resource_id: UUID | None = None, academic_term_id: UUID | None = None, exception_date: date | None = None, is_active: bool | None = True, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(user, resource_type, "read"); return service.date_exceptions(db, resource_type, resource_id, academic_term_id, exception_date, is_active)


@router.post("/date-exceptions", response_model=ResourceDateExceptionResponse, status_code=201)
def create_date_exception(payload: ResourceDateExceptionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(user, payload.resource_type, "manage"); return service.create_date_exception(db, payload)


@router.delete("/date-exceptions/{exception_id}", status_code=204)
def delete_date_exception(exception_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(ResourceDateException, exception_id)
    if item is None: raise HTTPException(404, "Resource date exception not found")
    authorize(user, item.resource_type, "manage"); service.delete_date_exception(db, exception_id); return Response(status_code=204)
