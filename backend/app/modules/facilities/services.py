from fastapi import HTTPException
from sqlalchemy import func,or_,select
from datetime import datetime,timezone
from app.modules.departments.models import Department
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.resource_availability.models import ResourceAvailabilityProfile,ResourceAvailabilitySlot
class FacilitiesService:
 def _model(self,n):return Classroom if n=="classroom" else Laboratory
 def _get(self,db,m,id):
  x=db.scalar(select(m).where(m.id==id))
  if not x:raise HTTPException(404,"Resource not found")
  return x
 def list(self,db,m,page,size,search=None,**f):
  q=select(m);cols=[m.room_number]+(([m.room_name,m.building_name]) if m is Classroom else [m.laboratory_code,m.laboratory_name])
  if search:q=q.where(or_(*[c.ilike(f"%{search}%") for c in cols if c is not None]))
  for k,v in f.items():
   if v is not None:q=q.where(getattr(m,k)==v)
  total=int(db.scalar(select(func.count()).select_from(q.subquery()))or 0);return {"items":list(db.scalars(q.offset((page-1)*size).limit(size))),"total":total,"page":page,"page_size":size,"pages":(total+size-1)//size}
 def save(self,db,m,data,id=None):
  old_mode=None
  if m is Laboratory:
   mode=data.get("availability_mode")
   if mode is None:mode="ALL_PERIODS" if data.get("is_available_all_periods",True) else "EXCEPT_BLOCKED"
   if mode not in {"ALL_PERIODS","EXCEPT_BLOCKED","ONLY_SELECTED"}:raise HTTPException(422,"LAB_INVALID_AVAILABILITY_MODE: availability_mode is invalid")
   data["availability_mode"]=mode;data["is_available_all_periods"]=mode=="ALL_PERIODS"
  if data.get("owning_department_id"):
   d=db.scalar(select(Department).where(Department.id==data["owning_department_id"]))
   if not d or not d.is_active:raise HTTPException(422,"Owning department must be active")
  x=self._get(db,m,id) if id else m();old_mode=getattr(x,"availability_mode",None) if m is Laboratory else None
  for k,v in data.items():setattr(x,k,v)
  db.add(x)
  if m is Laboratory and id and old_mode!=data["availability_mode"]:
   now=datetime.now(timezone.utc)
   for profile in db.scalars(select(ResourceAvailabilityProfile).where(ResourceAvailabilityProfile.resource_type=="LABORATORY",ResourceAvailabilityProfile.resource_id==x.id,ResourceAvailabilityProfile.is_active.is_(True))):profile.availability_mode=data["availability_mode"];profile.updated_at=now
   for slot in db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type=="LABORATORY",ResourceAvailabilitySlot.resource_id==x.id,ResourceAvailabilitySlot.is_active.is_(True))):slot.is_active=False;slot.updated_at=now
  try:db.commit()
  except Exception as e:db.rollback();raise HTTPException(409,"Duplicate resource") from e
  db.refresh(x);return x
 def delete(self,db,m,id):x=self._get(db,m,id);x.is_active=False;db.commit()
 def restore(self,db,m,id):x=self._get(db,m,id);x.is_active=True;db.commit();db.refresh(x);return x
facilities_service=FacilitiesService()
