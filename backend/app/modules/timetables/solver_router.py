from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user,require_permission
from app.modules.authentication.models import User
from app.modules.timetables.solver_repository import solver_run_repository
from app.modules.timetables.solver_schemas import SolveRequest,SolverQualityResponse,SolverRunPage,SolverRunResponse
from app.modules.timetables.solver_service import solver_service

version_solver_router=APIRouter(prefix="/timetable-versions",tags=["timetable-solver"]);solver_run_router=APIRouter(prefix="/solver-runs",tags=["timetable-solver"])
read=Depends(require_permission("timetable_solver","read"));run_permission=Depends(require_permission("timetable_solver","run"))

@version_solver_router.post("/{version_id}/solve",response_model=SolverRunResponse,status_code=201,dependencies=[run_permission])
def solve(version_id:UUID,payload:SolveRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return solver_service.solve(db,version_id,user.id,payload.time_limit_seconds,payload.random_seed,payload.optimization_profile,payload.weight_overrides)

@version_solver_router.get("/{version_id}/solver-runs",response_model=SolverRunPage,dependencies=[read])
def list_runs(version_id:UUID,db:Session=Depends(get_db),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return solver_run_repository.list(db,page,page_size,timetable_version_id=version_id)

@solver_run_router.get("",response_model=SolverRunPage,dependencies=[read])
def list_all_runs(db:Session=Depends(get_db),timetable_version_id:UUID|None=None,status:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):return solver_run_repository.list(db,page,page_size,timetable_version_id=timetable_version_id,status=status)

@solver_run_router.get("/{solver_run_id}",response_model=SolverRunResponse,dependencies=[read])
def get_run(solver_run_id:UUID,db:Session=Depends(get_db)):
 run=solver_run_repository.get(db,solver_run_id)
 if not run:raise HTTPException(404,"Solver run not found")
 return run

@solver_run_router.get("/{solver_run_id}/quality",response_model=SolverQualityResponse,dependencies=[read])
def get_quality(solver_run_id:UUID,db:Session=Depends(get_db)):
 run=solver_run_repository.get(db,solver_run_id)
 if not run:raise HTTPException(404,"Solver run not found")
 metrics=(run.statistics_json or {}).get("quality_metrics")
 if not metrics:raise HTTPException(409,"Quality metrics are unavailable for this solver run")
 return {"solver_run_id":run.id,**metrics}
