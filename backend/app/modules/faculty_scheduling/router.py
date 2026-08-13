from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.faculty_scheduling.schemas import AvailabilityBulk,AvailabilityCreate,AvailabilityRead,AvailabilityUpdate,PolicyCreate,PolicyRead,PolicyUpdate
from app.modules.faculty_scheduling.services import scheduling_service as s
availability=APIRouter(prefix="/faculty-availability",tags=["faculty availability"]);policies=APIRouter(prefix="/faculty-scheduling-policies",tags=["faculty scheduling policies"]);read=Depends(require_permission("faculty_availability","read"));manage=Depends(require_permission("faculty_availability","manage"));router=APIRouter()
@availability.get("",dependencies=[read])
def la(db:Session=Depends(get_db),faculty_id:UUID|None=None,academic_term_id:UUID|None=None,day_of_week:str|None=None,period_number:int|None=Query(None,ge=1,le=7),availability_type:str|None=None,is_active:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return s.list_availability(db,faculty_id=faculty_id,academic_term_id=academic_term_id,day_of_week=day_of_week,period_number=period_number,availability_type=availability_type,is_active=is_active,page=page,page_size=page_size)
@availability.post("/bulk",response_model=list[AvailabilityRead],status_code=201,dependencies=[manage])
def ba(v:AvailabilityBulk,db:Session=Depends(get_db)):return s.bulk(db,v)
@availability.get("/{id}",response_model=AvailabilityRead,dependencies=[read])
def ga(id:UUID,db:Session=Depends(get_db)):return s.get_availability(db,id)
@availability.post("",response_model=AvailabilityRead,status_code=201,dependencies=[manage])
def ca(v:AvailabilityCreate,db:Session=Depends(get_db)):return s.create_availability(db,v)
@availability.put("/{id}",response_model=AvailabilityRead,dependencies=[manage])
def ua(id:UUID,v:AvailabilityUpdate,db:Session=Depends(get_db)):return s.update_availability(db,id,v)
@availability.delete("/{id}",status_code=204,dependencies=[manage])
def da(id:UUID,db:Session=Depends(get_db)):s.delete_availability(db,id);return Response(status_code=204)
@availability.post("/{id}/restore",response_model=AvailabilityRead,dependencies=[manage])
def ra(id:UUID,db:Session=Depends(get_db)):return s.restore_availability(db,id)
@policies.get("",dependencies=[read])
def lp(db:Session=Depends(get_db),faculty_id:UUID|None=None,academic_term_id:UUID|None=None,is_active:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return s.list_policies(db,faculty_id=faculty_id,academic_term_id=academic_term_id,is_active=is_active,page=page,page_size=page_size)
@policies.get("/{id}",response_model=PolicyRead,dependencies=[read])
def gp(id:UUID,db:Session=Depends(get_db)):return s.get_policy(db,id)
@policies.post("",response_model=PolicyRead,status_code=201,dependencies=[manage])
def cp(v:PolicyCreate,db:Session=Depends(get_db)):return s.create_policy(db,v)
@policies.put("/{id}",response_model=PolicyRead,dependencies=[manage])
def up(id:UUID,v:PolicyUpdate,db:Session=Depends(get_db)):return s.update_policy(db,id,v)
@policies.delete("/{id}",status_code=204,dependencies=[manage])
def dp(id:UUID,db:Session=Depends(get_db)):s.delete_policy(db,id);return Response(status_code=204)
@policies.post("/{id}/restore",response_model=PolicyRead,dependencies=[manage])
def rp(id:UUID,db:Session=Depends(get_db)):return s.restore_policy(db,id)
router.include_router(availability);router.include_router(policies)
