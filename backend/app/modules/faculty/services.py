"""Faculty use cases."""
from math import ceil
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.departments.models import Department
from app.modules.faculty.models import Faculty
from app.modules.faculty.repositories import FacultyRepository
from app.modules.faculty.schemas import FacultyCreate, FacultyPage, FacultyUpdate
class FacultyService:
    def __init__(self): self.repository=FacultyRepository()
    def list_faculty(self,db,**filters):
        page,size=filters.pop("page"),filters.pop("page_size"); items,total=self.repository.list(db,**filters,offset=(page-1)*size,limit=size); return FacultyPage(items=items,total=total,page=page,page_size=size,pages=ceil(total/size) if total else 0)
    def get(self,db,id):
        value=self.repository.get(db,id)
        if not value: raise HTTPException(status_code=404,detail="Faculty not found")
        return value
    def create(self,db,payload):
        values=payload.model_dump(); self._validate(db,values); values["institutional_email"]=str(values["institutional_email"]).lower(); return self.repository.save(db,Faculty(**values))
    def update(self,db,id,payload):
        entity=self.get(db,id); values={f:getattr(entity,f) for f in ("faculty_code","department_id","institutional_email","user_id","minimum_weekly_workload","maximum_weekly_workload","maximum_periods_per_day")}; values.update(payload.model_dump(exclude_unset=True)); self._validate(db,values,entity.id)
        for f,v in payload.model_dump(exclude_unset=True).items(): setattr(entity,f, str(v).lower() if f=="institutional_email" else v)
        return self.repository.save(db,entity)
    def delete(self,db,id): entity=self.get(db,id); entity.is_active=False; return self.repository.save(db,entity)
    def restore(self,db,id):
        entity=self.get(db,id); self._active_department(db,entity.department_id); entity.is_active=True; return self.repository.save(db,entity)
    def _validate(self,db,v,exclude=None):
        self._active_department(db,v["department_id"])
        if v["maximum_weekly_workload"]<v["minimum_weekly_workload"]: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,detail="Invalid workload range")
        for getter,key,value,label in ((self.repository.by_code,"faculty_code",v["faculty_code"],"Faculty code"),(self.repository.by_email,"institutional_email",str(v["institutional_email"]),"Institutional email")):
            x=getter(db,value)
            if x and x.id!=exclude: raise HTTPException(status_code=409,detail=f"{label} already exists")
        if v.get("user_id"):
            x=self.repository.by_user(db,v["user_id"])
            if x and x.id!=exclude: raise HTTPException(status_code=409,detail="User is already linked to faculty")
    def _active_department(self,db,id):
        d=db.scalar(select(Department).where(Department.id==id))
        if not d or not d.is_active: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,detail="Department must exist and be active")
faculty_service=FacultyService()
