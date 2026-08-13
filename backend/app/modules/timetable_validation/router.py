from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user,require_permission
from app.modules.authentication.models import User
from app.modules.timetable_validation.models import ValidationRun,ValidationIssue
from app.modules.timetable_validation.repository import repo
from app.modules.timetable_validation.schemas import *
from app.modules.timetable_validation.service import validate
router=APIRouter(prefix="/timetable-validation",tags=["timetable-validation"]);read=Depends(require_permission("timetable_validation","read"));runp=Depends(require_permission("timetable_validation","run"))
@router.post("/run",response_model=ValidationRunSummary,status_code=201,dependencies=[runp])
def run(v:ValidationRunRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 issues,total_checks=validate(db,v);x=repo.create_run(db,**v.model_dump(),status="PASSED",total_checks=0,passed_checks=0,failed_checks=0,warning_checks=0,created_by=user.id);repo.create_issues(db,x.id,issues);return repo.finalize(db,x,issues,total_checks)
@router.get("/runs",response_model=ValidationRunPage,dependencies=[read])
def runs(db:Session=Depends(get_db),academic_term_id:UUID|None=None,scope_type:str|None=None,status:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
 items,total,pages=repo.page(db,ValidationRun,page,page_size,academic_term_id=academic_term_id,scope_type=scope_type,status=status);return {"items":items,"total":total,"page":page,"page_size":page_size,"pages":pages}
@router.get("/runs/{id}",response_model=ValidationRunDetail,dependencies=[read])
def getrun(id:UUID,db:Session=Depends(get_db)):
 x=db.scalar(__import__("sqlalchemy").select(ValidationRun).where(ValidationRun.id==id));
 if not x:raise HTTPException(404,"Validation run not found")
 return {**ValidationRunSummary.model_validate(x).model_dump(),"issues":list(db.scalars(__import__("sqlalchemy").select(ValidationIssue).where(ValidationIssue.validation_run_id==id)))}
@router.get("/runs/{id}/issues",response_model=ValidationIssuePage,dependencies=[read])
def issues(id:UUID,db:Session=Depends(get_db),severity:str|None=None,issue_code:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
 items,total,pages=repo.page(db,ValidationIssue,page,page_size,validation_run_id=id,severity=severity,issue_code=issue_code);return {"items":items,"total":total,"page":page,"page_size":page_size,"pages":pages}
