from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.facilities.schemas import *
from app.modules.facilities.services import facilities_service as s
router=APIRouter();c=APIRouter(prefix="/classrooms",tags=["classrooms"]);l=APIRouter(prefix="/laboratories",tags=["laboratories"]);cr=Depends(require_permission("classrooms","read"));cm=Depends(require_permission("classrooms","manage"));lr=Depends(require_permission("laboratories","read"));lm=Depends(require_permission("laboratories","manage"))
@c.get("",dependencies=[cr])
def lc(db:Session=Depends(get_db),search:str|None=None,owning_department_id:UUID|None=None,is_primary_classroom:bool|None=None,is_shareable:bool|None=None,is_active:bool|None=None,page:int=1,page_size:int=20):return s.list(db,Classroom,page,page_size,search,owning_department_id=owning_department_id,is_primary_classroom=is_primary_classroom,is_shareable=is_shareable,is_active=is_active)
@c.get("/{id}",response_model=ClassroomResponse,dependencies=[cr])
def gc(id:UUID,db:Session=Depends(get_db)):return s._get(db,Classroom,id)
@c.post("",response_model=ClassroomResponse,status_code=201,dependencies=[cm])
def cc(v:ClassroomCreate,db:Session=Depends(get_db)):return s.save(db,Classroom,v.model_dump())
@c.put("/{id}",response_model=ClassroomResponse,dependencies=[cm])
def uc(id:UUID,v:ClassroomUpdate,db:Session=Depends(get_db)):return s.save(db,Classroom,v.model_dump(),id)
@c.delete("/{id}",status_code=204,dependencies=[cm])
def dc(id:UUID,db:Session=Depends(get_db)):s.delete(db,Classroom,id);return Response(status_code=204)
@c.post("/{id}/restore",response_model=ClassroomResponse,dependencies=[cm])
def rc(id:UUID,db:Session=Depends(get_db)):return s.restore(db,Classroom,id)
@l.get("",dependencies=[lr])
def ll(db:Session=Depends(get_db),search:str|None=None,owning_department_id:UUID|None=None,is_shareable_across_departments:bool|None=None,is_available_all_periods:bool|None=None,availability_mode:str|None=None,concurrent_usage_mode:str|None=None,is_active:bool|None=None,page:int=1,page_size:int=20):return s.list(db,Laboratory,page,page_size,search,owning_department_id=owning_department_id,is_shareable_across_departments=is_shareable_across_departments,is_available_all_periods=is_available_all_periods,availability_mode=availability_mode,concurrent_usage_mode=concurrent_usage_mode,is_active=is_active)
@l.get("/{id}",response_model=LaboratoryResponse,dependencies=[lr])
def gl(id:UUID,db:Session=Depends(get_db)):return s._get(db,Laboratory,id)
@l.post("",response_model=LaboratoryResponse,status_code=201,dependencies=[lm])
def cl(v:LaboratoryCreate,db:Session=Depends(get_db)):return s.save(db,Laboratory,v.model_dump())
@l.put("/{id}",response_model=LaboratoryResponse,dependencies=[lm])
def ul(id:UUID,v:LaboratoryUpdate,db:Session=Depends(get_db)):return s.save(db,Laboratory,v.model_dump(),id)
@l.delete("/{id}",status_code=204,dependencies=[lm])
def dl(id:UUID,db:Session=Depends(get_db)):s.delete(db,Laboratory,id);return Response(status_code=204)
@l.post("/{id}/restore",response_model=LaboratoryResponse,dependencies=[lm])
def rl(id:UUID,db:Session=Depends(get_db)):return s.restore(db,Laboratory,id)
router.include_router(c);router.include_router(l)
