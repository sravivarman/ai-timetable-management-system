from datetime import date
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Response,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user,require_permission
from app.modules.authentication.models import User
from app.modules.timetables.entry_repository import entry_repository
from app.modules.timetables.entry_schemas import TimetableEntryCreate,TimetableEntryPage,TimetableEntryResponse,TimetableEntryUpdate
from app.modules.timetables.entry_service import entry_service

version_entry_router=APIRouter(prefix="/timetable-versions",tags=["timetable-entries"])
entry_router=APIRouter(prefix="/timetable-entries",tags=["timetable-entries"])
read=Depends(require_permission("timetable_entries","read"));manage=Depends(require_permission("timetable_entries","manage"))

@version_entry_router.get("/{version_id}/entries",response_model=TimetableEntryPage,dependencies=[read])
def list_entries(version_id:UUID,db:Session=Depends(get_db),course_offering_id:UUID|None=None,section_id:UUID|None=None,faculty_id:UUID|None=None,classroom_id:UUID|None=None,laboratory_id:UUID|None=None,student_batch_id:UUID|None=None,working_day_id:UUID|None=None,actual_date:date|None=None,period_number:int|None=Query(default=None,ge=1,le=7),entry_type:str|None=None,is_manual:bool|None=None,is_locked:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
 return entry_repository.list(db,version_id,page,page_size,course_offering_id=course_offering_id,section_id=section_id,faculty_id=faculty_id,classroom_id=classroom_id,laboratory_id=laboratory_id,student_batch_id=student_batch_id,working_day_id=working_day_id,actual_date=actual_date,period_number=period_number,entry_type=entry_type,is_manual=is_manual,is_locked=is_locked)

@version_entry_router.post("/{version_id}/entries",response_model=TimetableEntryResponse,status_code=201,dependencies=[manage])
def create_entry(version_id:UUID,payload:TimetableEntryCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return entry_service.create(db,version_id,payload,user.id)

@entry_router.get("/{entry_id}",response_model=TimetableEntryResponse,dependencies=[read])
def get_entry(entry_id:UUID,db:Session=Depends(get_db)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 return entry

@entry_router.put("/{entry_id}",response_model=TimetableEntryResponse,dependencies=[manage])
def update_entry(entry_id:UUID,payload:TimetableEntryUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 return entry_service.update(db,entry,payload,user.id)

@entry_router.delete("/{entry_id}",status_code=status.HTTP_204_NO_CONTENT,dependencies=[manage])
def delete_entry(entry_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 entry_service.delete(db,entry,user.id);return Response(status_code=status.HTTP_204_NO_CONTENT)
