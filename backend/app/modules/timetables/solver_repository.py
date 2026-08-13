from math import ceil
from sqlalchemy import func,select
from app.modules.timetables.models import SolverRun

class SolverRunRepository:
 def get(self,db,run_id):return db.scalar(select(SolverRun).where(SolverRun.id==run_id))
 def list(self,db,page,page_size,timetable_version_id=None,status=None):
  filters=[]
  if timetable_version_id is not None:filters.append(SolverRun.timetable_version_id==timetable_version_id)
  if status is not None:filters.append(SolverRun.status==status)
  query=select(SolverRun).where(*filters).order_by(SolverRun.created_at.desc(),SolverRun.id.desc());total=int(db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))or 0);return {"items":list(db.scalars(query.offset((page-1)*page_size).limit(page_size))),"total":total,"page":page,"page_size":page_size,"pages":ceil(total/page_size)if total else 0}

solver_run_repository=SolverRunRepository()
