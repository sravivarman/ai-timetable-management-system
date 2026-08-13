from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.facilities_constraints.models import *
from app.modules.facilities_constraints.schemas import *
from app.modules.sections.models import Section
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.academic_terms.models import AcademicTerm
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.resource_availability.schemas import ResourceAvailabilitySlotCreate
from app.modules.resource_availability.service import availability_service
router=APIRouter(tags=["facilities-constraints"])
def dep(r,a):return Depends(require_permission(r,a))
def get(db,m,id):
 x=db.scalar(select(m).where(m.id==id))
 if not x:raise HTTPException(404,"Record not found")
 return x
def save(db,x):db.add(x);db.commit();db.refresh(x);return x
def get_lab_slot(db,id):
 x=availability_service.get_slot(db,id)
 if x.resource_type!="LABORATORY":raise HTTPException(404,"Record not found")
 return x
def list_(db,m,page,ps,**f):
 q=select(m)
 for k,v in f.items():
  if v is not None:q=q.where(getattr(m,k)==v)
 return {"items":list(db.scalars(q.offset((page-1)*ps).limit(ps))),"total":int(db.scalar(select(func.count()).select_from(q.subquery()))or 0),"page":page,"page_size":ps}
@router.get("/section-classroom-assignments",dependencies=[dep("section_classrooms","read")])
def la(db:Session=Depends(get_db),section_id:UUID|None=None,classroom_id:UUID|None=None,academic_term_id:UUID|None=None,is_primary:bool|None=None,is_active:bool|None=True,page:int=1,page_size:int=20):return list_(db,SectionClassroomAssignment,page,page_size,section_id=section_id,classroom_id=classroom_id,academic_term_id=academic_term_id,is_primary=is_primary,is_active=is_active)
@router.post("/section-classroom-assignments",response_model=AssignmentRead,status_code=201,dependencies=[dep("section_classrooms","manage")])
def ca(v:AssignmentCreate,db:Session=Depends(get_db)):
 s=get(db,Section,v.section_id);c=get(db,Classroom,v.classroom_id);t=get(db,AcademicTerm,v.academic_term_id)
 if not(s.is_active and c.is_active and t.is_active)or s.academic_term_id!=t.id:raise HTTPException(422,"Active matching section, classroom, and term are required")
 if db.scalar(select(SectionClassroomAssignment).where(SectionClassroomAssignment.section_id==v.section_id,SectionClassroomAssignment.classroom_id==v.classroom_id,SectionClassroomAssignment.academic_term_id==v.academic_term_id)):raise HTTPException(409,"Classroom assignment already exists")
 if v.is_primary and db.scalar(select(SectionClassroomAssignment).where(SectionClassroomAssignment.section_id==v.section_id,SectionClassroomAssignment.academic_term_id==v.academic_term_id,SectionClassroomAssignment.is_primary.is_(True),SectionClassroomAssignment.is_active.is_(True))):raise HTTPException(409,"Active primary classroom already exists")
 return save(db,SectionClassroomAssignment(**v.model_dump()))
@router.get("/section-classroom-assignments/{id}",response_model=AssignmentRead,dependencies=[dep("section_classrooms","read")])
def ga(id:UUID,db:Session=Depends(get_db)):return get(db,SectionClassroomAssignment,id)
@router.put("/section-classroom-assignments/{id}",response_model=AssignmentRead,dependencies=[dep("section_classrooms","manage")])
def ua(id:UUID,v:AssignmentUpdate,db:Session=Depends(get_db)):x=get(db,SectionClassroomAssignment,id);[setattr(x,k,z)for k,z in v.model_dump(exclude_unset=True).items()];return save(db,x)
@router.delete("/section-classroom-assignments/{id}",status_code=204,dependencies=[dep("section_classrooms","manage")])
def da(id:UUID,db:Session=Depends(get_db)):x=get(db,SectionClassroomAssignment,id);x.is_active=False;save(db,x);return Response(status_code=204)
@router.post("/section-classroom-assignments/{id}/restore",response_model=AssignmentRead,dependencies=[dep("section_classrooms","manage")])
def ra(id:UUID,db:Session=Depends(get_db)):x=get(db,SectionClassroomAssignment,id);x.is_active=True;return save(db,x)
@router.get("/laboratory-availability-blocks",dependencies=[dep("laboratory_blocks","read")])
def lb(db:Session=Depends(get_db),laboratory_id:UUID|None=None,academic_term_id:UUID|None=None,working_day_id:UUID|None=None,period_number:int|None=None,availability_type:str|None=None,is_active:bool|None=True,page:int=1,page_size:int=20):return list_(db,LaboratoryAvailabilityBlock,page,page_size,resource_type="LABORATORY",laboratory_id=laboratory_id,academic_term_id=academic_term_id,working_day_id=working_day_id,period_number=period_number,availability_type=availability_type,is_active=is_active)
@router.post("/laboratory-availability-blocks",response_model=BlockRead,status_code=201,dependencies=[dep("laboratory_blocks","manage")])
def cb(v:BlockCreate,db:Session=Depends(get_db)):
 payload=ResourceAvailabilitySlotCreate(resource_type="LABORATORY",resource_id=v.laboratory_id,**v.model_dump(exclude={"laboratory_id"}))
 try:return availability_service.create_slot(db,payload)
 except HTTPException as error:
  if isinstance(error.detail,str):error.detail=error.detail.replace("RESOURCE_AVAILABILITY_CONFLICT","LAB_AVAILABILITY_CONFLICT")
  raise
@router.get("/laboratory-availability-blocks/{id}",response_model=BlockRead,dependencies=[dep("laboratory_blocks","read")])
def gb(id:UUID,db:Session=Depends(get_db)):return get_lab_slot(db,id)
@router.put("/laboratory-availability-blocks/{id}",response_model=BlockRead,dependencies=[dep("laboratory_blocks","manage")])
def ub(id:UUID,v:BlockUpdate,db:Session=Depends(get_db)):
 x=get_lab_slot(db,id)
 from app.modules.resource_availability.schemas import ResourceAvailabilitySlotUpdate
 return availability_service.update_slot(db,id,ResourceAvailabilitySlotUpdate(**v.model_dump(exclude_unset=True)))
@router.delete("/laboratory-availability-blocks/{id}",status_code=204,dependencies=[dep("laboratory_blocks","manage")])
def db_(id:UUID,db:Session=Depends(get_db)):get_lab_slot(db,id);availability_service.delete_slot(db,id);return Response(status_code=204)
@router.post("/laboratory-availability-blocks/{id}/restore",response_model=BlockRead,dependencies=[dep("laboratory_blocks","manage")])
def rb(id:UUID,db:Session=Depends(get_db)):
 get_lab_slot(db,id);return availability_service.restore_slot(db,id)
