from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user,require_permission
from app.modules.authentication.models import User
from app.modules.academic_terms.models import AcademicTerm
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.models import Timetable,TimetableVersion
from app.modules.timetables.repository import repo
from app.modules.timetables.schemas import *
from app.modules.timetables.service import solver_input_builder
from app.modules.scheduling_slots.models import SchedulingSlot
router=APIRouter(prefix="/timetables",tags=["timetables"]);read=Depends(require_permission("timetables","read"));manage=Depends(require_permission("timetables","manage"))
version_router=APIRouter(prefix="/timetable-versions",tags=["timetables"])
solver_read=Depends(require_permission("solver_inputs","read"));solver_build=Depends(require_permission("solver_inputs","build"))
def scope(v):
 ok={"COLLEGE":not any((v.department_id,v.program_id,v.section_id)),"DEPARTMENT":v.department_id and not v.program_id and not v.section_id,"PROGRAM":v.program_id and not v.department_id and not v.section_id,"SECTION":v.section_id and not v.department_id and not v.program_id}
 if not ok.get(v.scope_type):raise HTTPException(422,"Scope IDs do not match scope type")
def scheduling(db,v):
 if v.scheduling_mode=="WEEKLY":
  if v.scheduling_slot_id is not None:raise HTTPException(422,"WEEKLY timetables must not specify a Scheduling Slot")
  return
 if v.scheduling_mode!="SLOT_BASED" or v.scheduling_slot_id is None:raise HTTPException(422,"SLOT_BASED timetables require a Scheduling Slot")
 slot=repo.get(db,SchedulingSlot,v.scheduling_slot_id)
 if not slot or not slot.is_active:raise HTTPException(422,"Scheduling Slot must be active")
 if slot.academic_term_id!=v.academic_term_id:raise HTTPException(422,"Scheduling Slot Academic Term does not match timetable")
@router.post("",response_model=TimetableResponse,status_code=201,dependencies=[manage])
def create(v:TimetableCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 scope(v);scheduling(db,v);term=repo.get(db,AcademicTerm,v.academic_term_id)
 if not term or not term.is_active:raise HTTPException(422,"Academic term must be active")
 now=datetime.now(timezone.utc)
 return repo.save(db,Timetable(**v.model_dump(),created_by=user.id,created_at=now,updated_at=now))
@router.get("",response_model=TimetablePage,dependencies=[read])
def list_(db:Session=Depends(get_db),academic_term_id:UUID|None=None,scope_type:str|None=None,department_id:UUID|None=None,program_id:UUID|None=None,section_id:UUID|None=None,scheduling_mode:str|None=None,scheduling_slot_id:UUID|None=None,status:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return repo.page(db,Timetable,page,page_size,academic_term_id=academic_term_id,scope_type=scope_type,department_id=department_id,program_id=program_id,section_id=section_id,scheduling_mode=scheduling_mode,scheduling_slot_id=scheduling_slot_id,status=status)
@router.get("/{id}",response_model=TimetableResponse,dependencies=[read])
def get_(id:UUID,db:Session=Depends(get_db)):
 x=repo.get(db,Timetable,id)
 if not x:raise HTTPException(404,"Timetable not found")
 return x
@router.put("/{id}",response_model=TimetableResponse,dependencies=[manage])
def update(id:UUID,v:TimetableUpdate,db:Session=Depends(get_db)):
 x=repo.get(db,Timetable,id)
 if not x:raise HTTPException(404,"Timetable not found")
 if x.status in {"APPROVED","PUBLISHED","ARCHIVED"}:raise HTTPException(409,"Immutable timetable")
 for k,z in v.model_dump(exclude_unset=True).items():setattr(x,k,z)
 x.updated_at=datetime.now(timezone.utc)
 return repo.save(db,x)
@router.post("/{id}/versions",response_model=TimetableVersionResponse,status_code=201,dependencies=[manage])
def version(id:UUID,v:TimetableVersionCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 t=repo.get(db,Timetable,id);run=repo.get(db,ValidationRun,v.validation_run_id)
 if not t:raise HTTPException(404,"Timetable not found")
 if not run:raise HTTPException(422,"Validation run not found")
 if run.status not in {"PASSED","WARNING"}:raise HTTPException(422,"Validation run must have PASSED or WARNING status")
 if run.academic_term_id!=t.academic_term_id or any(getattr(run,field)!=getattr(t,field) for field in ("scope_type","department_id","program_id","section_id","scheduling_mode","scheduling_slot_id")):raise HTTPException(422,"Validation run must match timetable scope, mode, Slot, and Academic Term")
 for old in db.scalars(select(TimetableVersion).where(TimetableVersion.timetable_id==id,TimetableVersion.is_active.is_(True))):old.is_active=False
 number=int(db.scalar(select(func.max(TimetableVersion.version_number)).where(TimetableVersion.timetable_id==id))or 0)+1;now=datetime.now(timezone.utc);x=TimetableVersion(timetable_id=id,version_number=number,validation_run_id=v.validation_run_id,version_name=v.version_name,source_type=v.source_type,scheduling_mode=t.scheduling_mode,scheduling_slot_id=t.scheduling_slot_id,created_by=user.id,solver_status="NOT_STARTED",created_at=now,updated_at=now);db.add(x);db.flush();t.active_version_id=x.id;t.updated_at=now;db.commit();db.refresh(x);return x
@router.get("/{id}/versions",response_model=TimetableVersionPage,dependencies=[read])
def versions(id:UUID,db:Session=Depends(get_db),solver_status:str|None=None,is_active:bool|None=None,is_locked:bool|None=None,page:int=1,page_size:int=20):return repo.page(db,TimetableVersion,page,page_size,timetable_id=id,solver_status=solver_status,is_active=is_active,is_locked=is_locked)
@version_router.get("/{version_id}",response_model=TimetableVersionResponse,dependencies=[read])
def get_version(version_id:UUID,db:Session=Depends(get_db)):
 x=repo.get(db,TimetableVersion,version_id)
 if not x:raise HTTPException(404,"Timetable version not found")
 return x
@version_router.post("/{version_id}/build-solver-input",response_model=SolverInputSnapshotResponse,status_code=201,dependencies=[solver_build])
def build_solver_input(version_id:UUID,db:Session=Depends(get_db)):
 return solver_input_builder.build(db,version_id)
@version_router.get("/{version_id}/solver-input",response_model=SolverInputSnapshotResponse,dependencies=[solver_read])
def get_solver_input(version_id:UUID,db:Session=Depends(get_db)):
 return solver_input_builder.latest(db,version_id)
