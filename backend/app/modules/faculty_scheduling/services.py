from math import ceil
from datetime import datetime,timezone
from uuid import UUID
from fastapi import HTTPException,status
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.modules.faculty.models import Faculty
from app.modules.academic_terms.models import AcademicTerm
from app.modules.faculty_scheduling.models import FacultyAvailability,FacultySchedulingPolicy
from app.modules.resource_availability.models import ResourceAvailabilityProfile,ResourceAvailabilitySlot
from app.modules.schedule_configuration.models import WorkingDay
class SchedulingService:
 def _deactivate_hard(self,db,faculty_id,term_id,day_name,period):
  day=db.scalar(select(WorkingDay).where(WorkingDay.day_name==day_name));now=datetime.now(timezone.utc)
  if day:
   for slot in db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type=="FACULTY",ResourceAvailabilitySlot.resource_id==faculty_id,ResourceAvailabilitySlot.academic_term_id==term_id,ResourceAvailabilitySlot.working_day_id==day.id,ResourceAvailabilitySlot.period_number==period,ResourceAvailabilitySlot.availability_type=="BLOCKED",ResourceAvailabilitySlot.is_active.is_(True))):slot.is_active=False;slot.updated_at=now
 def _sync_hard(self,db,x):
  if x.availability_type!="unavailable" or x.is_active is False:return
  day=db.scalar(select(WorkingDay).where(WorkingDay.day_name==x.day_of_week,WorkingDay.is_active.is_(True)))
  if not day:return
  now=datetime.now(timezone.utc);profile=db.scalar(select(ResourceAvailabilityProfile).where(ResourceAvailabilityProfile.resource_type=="FACULTY",ResourceAvailabilityProfile.resource_id==x.faculty_id,ResourceAvailabilityProfile.academic_term_id==x.academic_term_id,ResourceAvailabilityProfile.is_active.is_(True)))
  if not profile:db.add(ResourceAvailabilityProfile(resource_type="FACULTY",resource_id=x.faculty_id,academic_term_id=x.academic_term_id,availability_mode="EXCEPT_BLOCKED",created_at=now,updated_at=now))
  elif profile.availability_mode!="EXCEPT_BLOCKED":profile.availability_mode="EXCEPT_BLOCKED";profile.updated_at=now
  slot=db.scalar(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type=="FACULTY",ResourceAvailabilitySlot.resource_id==x.faculty_id,ResourceAvailabilitySlot.academic_term_id==x.academic_term_id,ResourceAvailabilitySlot.working_day_id==day.id,ResourceAvailabilitySlot.period_number==x.period_number,ResourceAvailabilitySlot.is_active.is_(True)))
  if not slot:db.add(ResourceAvailabilitySlot(resource_type="FACULTY",resource_id=x.faculty_id,academic_term_id=x.academic_term_id,working_day_id=day.id,period_number=x.period_number,availability_type="BLOCKED",reason=x.reason,created_at=now,updated_at=now))
 def _parents(self,db,f,t):
  faculty=db.scalar(select(Faculty).where(Faculty.id==f));term=db.scalar(select(AcademicTerm).where(AcademicTerm.id==t))
  if not faculty or not faculty.is_active:raise HTTPException(status_code=422,detail="Faculty must exist and be active")
  if not term or not term.is_active:raise HTTPException(status_code=422,detail="Academic term must exist and be active")
 def _page(self,stmt,db,page,size):
  total=int(db.scalar(select(func.count()).select_from(stmt.subquery()))or 0);return {"items":list(db.scalars(stmt.offset((page-1)*size).limit(size))),"total":total,"page":page,"page_size":size,"pages":ceil(total/size)if total else 0}
 def list_availability(self,db,**f):
  p,s=f.pop("page"),f.pop("page_size");stmt=select(FacultyAvailability)
  for c,v in ((FacultyAvailability.faculty_id,f.get("faculty_id")),(FacultyAvailability.academic_term_id,f.get("academic_term_id")),(FacultyAvailability.day_of_week,f.get("day_of_week")),(FacultyAvailability.period_number,f.get("period_number")),(FacultyAvailability.availability_type,f.get("availability_type")),(FacultyAvailability.is_active,f.get("is_active"))):
   if v is not None:stmt=stmt.where(c==v)
  return self._page(stmt.order_by(FacultyAvailability.day_of_week,FacultyAvailability.period_number),db,p,s)
 def get_availability(self,db,id):
  x=db.scalar(select(FacultyAvailability).where(FacultyAvailability.id==id))
  if not x:raise HTTPException(status_code=404,detail="Availability not found")
  return x
 def create_availability(self,db,v):
  self._parents(db,v.faculty_id,v.academic_term_id);self._avail_unique(db,v.faculty_id,v.academic_term_id,v.day_of_week,v.period_number);x=FacultyAvailability(**v.model_dump());db.add(x);self._sync_hard(db,x);db.commit();db.refresh(x);return x
 def bulk(self,db,v):
  slots=[(x.day_of_week,x.period_number) for x in v.records]
  if len(slots)!=len(set(slots)):raise HTTPException(status_code=422,detail="Duplicate weekly slots")
  self._parents(db,v.faculty_id,v.academic_term_id);items=[]
  for x in v.records:
   self._avail_unique(db,v.faculty_id,v.academic_term_id,x.day_of_week,x.period_number);items.append(FacultyAvailability(**x.model_dump()))
  db.add_all(items);[self._sync_hard(db,x) for x in items];db.commit();[db.refresh(x)for x in items];return items
 def update_availability(self,db,id,v):
  x=self.get_availability(db,id);old=(x.faculty_id,x.academic_term_id,x.day_of_week,x.period_number);d=v.model_dump(exclude_unset=True);day=d.get("day_of_week",x.day_of_week);period=d.get("period_number",x.period_number);self._avail_unique(db,x.faculty_id,x.academic_term_id,day,period,x.id);self._deactivate_hard(db,*old)
  for k,val in d.items():setattr(x,k,val)
  self._sync_hard(db,x);db.commit();db.refresh(x);return x
 def delete_availability(self,db,id):x=self.get_availability(db,id);x.is_active=False;self._deactivate_hard(db,x.faculty_id,x.academic_term_id,x.day_of_week,x.period_number);db.commit()
 def restore_availability(self,db,id):x=self.get_availability(db,id);self._parents(db,x.faculty_id,x.academic_term_id);self._avail_unique(db,x.faculty_id,x.academic_term_id,x.day_of_week,x.period_number,x.id);x.is_active=True;self._sync_hard(db,x);db.commit();db.refresh(x);return x
 def _avail_unique(self,db,f,t,d,p,exclude=None):
  x=db.scalar(select(FacultyAvailability).where(FacultyAvailability.faculty_id==f,FacultyAvailability.academic_term_id==t,FacultyAvailability.day_of_week==d,FacultyAvailability.period_number==p))
  if x and x.id!=exclude:raise HTTPException(status_code=409,detail="Availability already exists for this slot")
 def list_policies(self,db,**f):
  p,s=f.pop("page"),f.pop("page_size");stmt=select(FacultySchedulingPolicy)
  for c,v in ((FacultySchedulingPolicy.faculty_id,f.get("faculty_id")),(FacultySchedulingPolicy.academic_term_id,f.get("academic_term_id")),(FacultySchedulingPolicy.is_active,f.get("is_active"))):
   if v is not None:stmt=stmt.where(c==v)
  return self._page(stmt,db,p,s)
 def get_policy(self,db,id):
  x=db.scalar(select(FacultySchedulingPolicy).where(FacultySchedulingPolicy.id==id))
  if not x:raise HTTPException(status_code=404,detail="Scheduling policy not found")
  return x
 def create_policy(self,db,v):
  self._parents(db,v.faculty_id,v.academic_term_id)
  if db.scalar(select(FacultySchedulingPolicy).where(FacultySchedulingPolicy.faculty_id==v.faculty_id,FacultySchedulingPolicy.academic_term_id==v.academic_term_id)):raise HTTPException(status_code=409,detail="Policy already exists")
  x=FacultySchedulingPolicy(**v.model_dump());db.add(x);db.commit();db.refresh(x);return x
 def update_policy(self,db,id,v):
  x=self.get_policy(db,id)
  for k,val in v.model_dump(exclude_unset=True).items():setattr(x,k,val)
  db.commit();db.refresh(x);return x
 def delete_policy(self,db,id):x=self.get_policy(db,id);x.is_active=False;db.commit()
 def restore_policy(self,db,id):x=self.get_policy(db,id);self._parents(db,x.faculty_id,x.academic_term_id);x.is_active=True;db.commit();db.refresh(x);return x
scheduling_service=SchedulingService()
