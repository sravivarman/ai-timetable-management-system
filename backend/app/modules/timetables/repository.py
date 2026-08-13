from math import ceil
from sqlalchemy import func,select
from app.modules.timetables.models import Timetable,TimetableVersion,SolverInputSnapshot
class Repo:
 def get(self,db,m,id):return db.scalar(select(m).where(m.id==id))
 def save(self,db,x):db.add(x);db.commit();db.refresh(x);return x
 def page(self,db,m,page,ps,**f):
  q=select(m).where(*[getattr(m,k)==v for k,v in f.items()if v is not None]);total=int(db.scalar(select(func.count()).select_from(q.subquery()))or 0);return {"items":list(db.scalars(q.offset((page-1)*ps).limit(ps))),"total":total,"page":page,"page_size":ps,"pages":ceil(total/ps)if total else 0}
repo=Repo()
