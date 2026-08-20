from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
class TimetableCreate(BaseModel):
 academic_term_id:UUID;scope_type:Literal["COLLEGE","DEPARTMENT","PROGRAM","SECTION"];department_id:UUID|None=None;program_id:UUID|None=None;section_id:UUID|None=None;scheduling_mode:Literal["WEEKLY","SLOT_BASED"]="WEEKLY";scheduling_slot_id:UUID|None=None;name:str=Field(min_length=1,max_length=255)
 @model_validator(mode="after")
 def mode_slot(self):
  if self.scheduling_mode=="WEEKLY" and self.scheduling_slot_id is not None:raise ValueError("WEEKLY timetables must not specify a Scheduling Slot")
  if self.scheduling_mode=="SLOT_BASED" and self.scheduling_slot_id is None:raise ValueError("SLOT_BASED timetables require a Scheduling Slot")
  return self
class TimetableUpdate(BaseModel): name:str|None=Field(default=None,min_length=1,max_length=255);status:str|None=None
class TimetableResponse(TimetableCreate): model_config=ConfigDict(from_attributes=True);id:UUID;status:str;active_version_id:UUID|None;created_by:UUID;created_at:datetime;updated_at:datetime
class TimetableVersionCreate(BaseModel): validation_run_id:UUID;version_name:str|None=None;source_type:Literal["GENERATED","MANUAL_COPY","SEMESTER_COPY"]="GENERATED"
class TimetableVersionResponse(TimetableVersionCreate): model_config=ConfigDict(from_attributes=True);id:UUID;timetable_id:UUID;version_number:int;scheduling_mode:Literal["WEEKLY","SLOT_BASED"];scheduling_slot_id:UUID|None;solver_status:str;is_active:bool;is_locked:bool;created_by:UUID;created_at:datetime;updated_at:datetime
class SolverInputSnapshotResponse(BaseModel): model_config=ConfigDict(from_attributes=True);id:UUID;timetable_version_id:UUID;snapshot_json:dict;input_hash:str;created_at:datetime
class TimetablePage(BaseModel): items:list[TimetableResponse];total:int;page:int;page_size:int;pages:int
class TimetableVersionPage(BaseModel): items:list[TimetableVersionResponse];total:int;page:int;page_size:int;pages:int
