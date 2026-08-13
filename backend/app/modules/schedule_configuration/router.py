from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.schedule_configuration.models import WorkingDay,PeriodTiming
from app.modules.schedule_configuration.schemas import WorkingDayCreate,WorkingDayUpdate,WorkingDayRead,PeriodCreate,PeriodUpdate,PeriodRead
from app.modules.schedule_configuration.services import config_service as s
wd=APIRouter(prefix="/working-days",tags=["working days"]);pt=APIRouter(prefix="/period-timings",tags=["period timings"]);router=APIRouter();rd=Depends(require_permission("working_days","read"));md=Depends(require_permission("working_days","manage"));rp=Depends(require_permission("period_timings","read"));mp=Depends(require_permission("period_timings","manage"))
@wd.get("",dependencies=[rd])
def ld(db:Session=Depends(get_db),is_active:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return s.days(db,page,page_size,is_active)
@wd.get("/{id}",response_model=WorkingDayRead,dependencies=[rd])
def gd(id:UUID,db:Session=Depends(get_db)):return s._get(db,WorkingDay,id,"Working day")
@wd.post("",response_model=WorkingDayRead,status_code=201,dependencies=[md])
def cd(v:WorkingDayCreate,db:Session=Depends(get_db)):return s.create(db,WorkingDay,v)
@wd.put("/{id}",response_model=WorkingDayRead,dependencies=[md])
def ud(id:UUID,v:WorkingDayUpdate,db:Session=Depends(get_db)):return s.update(db,WorkingDay,id,v,"Working day")
@wd.delete("/{id}",status_code=204,dependencies=[md])
def dd(id:UUID,db:Session=Depends(get_db)):s.deactivate(db,WorkingDay,id,"Working day");return Response(status_code=204)
@wd.post("/{id}/restore",response_model=WorkingDayRead,dependencies=[md])
def rd_(id:UUID,db:Session=Depends(get_db)):return s.restore(db,WorkingDay,id,"Working day")
@pt.get("",dependencies=[rp])
def lp(db:Session=Depends(get_db),schedule_type:str|None=None,period_number:int|None=None,is_instructional:bool|None=None,break_type:str|None=None,is_active:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return s.periods(db,page,page_size,schedule_type=schedule_type,period_number=period_number,is_instructional=is_instructional,break_type=break_type,is_active=is_active)
@pt.post("",response_model=PeriodRead,status_code=201,dependencies=[mp])
def cp(v:PeriodCreate,db:Session=Depends(get_db)):return s.create(db,PeriodTiming,v)
@pt.get("/{id}",response_model=PeriodRead,dependencies=[rp])
def gp(id:UUID,db:Session=Depends(get_db)):return s._get(db,PeriodTiming,id,"Period timing")
@pt.put("/{id}",response_model=PeriodRead,dependencies=[mp])
def up(id:UUID,v:PeriodUpdate,db:Session=Depends(get_db)):return s.update(db,PeriodTiming,id,v,"Period timing")
@pt.delete("/{id}",status_code=204,dependencies=[mp])
def dp(id:UUID,db:Session=Depends(get_db)):s.deactivate(db,PeriodTiming,id,"Period timing");return Response(status_code=204)
@pt.post("/{id}/restore",response_model=PeriodRead,dependencies=[mp])
def rp_(id:UUID,db:Session=Depends(get_db)):return s.restore(db,PeriodTiming,id,"Period timing")
router.include_router(wd);router.include_router(pt)
