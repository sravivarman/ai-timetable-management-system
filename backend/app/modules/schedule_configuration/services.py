from fastapi import HTTPException
from sqlalchemy import func,select
from app.modules.schedule_configuration.models import WorkingDay,PeriodTiming
class ConfigService:
 def _get(self,db,model,id,label):
  x=db.scalar(select(model).where(model.id==id))
  if not x:raise HTTPException(status_code=404,detail=f"{label} not found")
  return x
 def _list(self,db,model,page,size,**f):
  q=select(model)
  for k,v in f.items():
   if v is not None:q=q.where(getattr(model,k)==v)
  total=int(db.scalar(select(func.count()).select_from(q.subquery()))or 0);return {"items":list(db.scalars(q.offset((page-1)*size).limit(size))),"total":total,"page":page,"page_size":size,"pages":(total+size-1)//size}
 def days(self,db,page,size,is_active=None):return self._list(db,WorkingDay,page,size,is_active=is_active)
 def periods(self,db,page,size,**f):return self._list(db,PeriodTiming,page,size,**f)
 def create(self,db,model,v):
  data=v.model_dump();x=model(**data);db.add(x)
  try:db.commit()
  except Exception as e:db.rollback();raise HTTPException(status_code=409,detail="Duplicate configuration") from e
  db.refresh(x);return x
 def update(self,db,model,id,v,label):
  x=self._get(db,model,id,label);data=v.model_dump(exclude_unset=True)
  if model is PeriodTiming and {"start_time","end_time","duration_minutes"}&set(data):
   st=data.get("start_time",x.start_time);et=data.get("end_time",x.end_time);du=data.get("duration_minutes",x.duration_minutes);m=(et.hour*60+et.minute)-(st.hour*60+st.minute)
   if m<=0 or m!=du:raise HTTPException(status_code=422,detail="Invalid period duration")
  for k,val in data.items():setattr(x,k,val)
  db.commit();db.refresh(x);return x
 def deactivate(self,db,model,id,label):x=self._get(db,model,id,label);x.is_active=False;db.commit()
 def restore(self,db,model,id,label):x=self._get(db,model,id,label);x.is_active=True;db.commit();db.refresh(x);return x
config_service=ConfigService()
