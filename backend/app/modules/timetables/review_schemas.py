from datetime import datetime,time
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field

class TimetableEntryMove(BaseModel):
 working_day_id:UUID;period_number:int=Field(ge=1,le=7);classroom_id:UUID|None=None;laboratory_id:UUID|None=None;lock_after_move:bool=True
class LockRequest(BaseModel): reason:str|None=Field(default=None,max_length=1000)
class UnlockRequest(BaseModel): reason:str=Field(min_length=1,max_length=1000)
class VersionCopyRequest(BaseModel): version_name:str=Field(min_length=1,max_length=255);source_type:Literal["MANUAL_COPY","SEMESTER_COPY"]="MANUAL_COPY"
class TransitionRequest(BaseModel): reason:str|None=Field(default=None,max_length=1000)
class RequiredReasonRequest(BaseModel): reason:str=Field(min_length=1,max_length=1000)

class TimetableGridEntry(BaseModel):
 entry_id:UUID;laboratory_rotation_block_id:UUID|None=None;combined_teaching_event_id:UUID|None=None;combined_teaching_group_code:str|None=None;combined_section_codes:list[str]=Field(default_factory=list);working_day_id:UUID;day_name:str;period_number:int;period_numbers:list[int];schedule_type:str;start_time:time;end_time:time
 course_code:str;course_name:str;course_type:str;section_code:str;faculty_code:str|None;faculty_name:str|None;classroom_room_number:str|None;laboratory_code:str|None;laboratory_name:str|None;batch_name:str|None;session_length:int;entry_status:str;is_manual:bool;is_locked:bool
class TimetableGridDay(BaseModel): working_day_id:UUID;day_name:str;sequence_number:int;entries:list[TimetableGridEntry]
class TimetableGridResponse(BaseModel): version_id:UUID;view_type:str;resource_id:UUID;schedule_type:str;days:list[TimetableGridDay]

class TimetableEntryAuditResponse(BaseModel):
 model_config=ConfigDict(from_attributes=True);id:UUID;timetable_entry_id:UUID;timetable_version_id:UUID;action_type:str;old_values_json:dict|None;new_values_json:dict|None;reason:str|None;performed_by:UUID;created_at:datetime
class TimetableStatusHistoryResponse(BaseModel):
 model_config=ConfigDict(from_attributes=True);id:UUID;timetable_id:UUID;from_status:str;to_status:str;reason:str|None;performed_by:UUID;created_at:datetime
class VersionComparisonResponse(BaseModel):
 version_id:UUID;other_version_id:UUID;added_entries:list[dict];removed_entries:list[dict];moved_entries:list[dict];faculty_changes:list[dict];facility_changes:list[dict];lock_state_changes:list[dict];summary:dict[str,int]
class FreeResourceResponse(BaseModel): version_id:UUID;working_day_id:UUID;period_number:int;items:list[dict]
class ConflictReportResponse(BaseModel): version_id:UUID;conflicts:list[dict];summary:dict[str,int]
