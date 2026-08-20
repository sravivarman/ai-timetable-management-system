from datetime import date,datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field

EntryType=Literal["THEORY","LABORATORY","PRACTICAL","CDC","LSM","MINI_PROJECT","PROJECT"]

class TimetableEntryCreate(BaseModel):
 course_offering_id:UUID;section_id:UUID;faculty_id:UUID|None=None;laboratory_faculty_allocation_id:UUID|None=None;classroom_id:UUID|None=None;laboratory_id:UUID|None=None;student_batch_id:UUID|None=None;laboratory_rotation_block_id:UUID|None=None;laboratory_rotation_assignment_id:UUID|None=None;combined_teaching_event_id:UUID|None=None;working_day_id:UUID;actual_date:date|None=None;period_number:int=Field(ge=1,le=7);session_length:Literal[1,2,3]=1;entry_type:EntryType;is_manual:bool=False;is_locked:bool=False

class TimetableEntryUpdate(BaseModel):
 course_offering_id:UUID|None=None;section_id:UUID|None=None;faculty_id:UUID|None=None;laboratory_faculty_allocation_id:UUID|None=None;classroom_id:UUID|None=None;laboratory_id:UUID|None=None;student_batch_id:UUID|None=None;laboratory_rotation_block_id:UUID|None=None;laboratory_rotation_assignment_id:UUID|None=None;combined_teaching_event_id:UUID|None=None;working_day_id:UUID|None=None;actual_date:date|None=None;period_number:int|None=Field(default=None,ge=1,le=7);session_length:Literal[1,2,3]|None=None;entry_type:EntryType|None=None;is_manual:bool|None=None;is_locked:bool|None=None

class TimetableEntryResponse(TimetableEntryCreate):
 model_config=ConfigDict(from_attributes=True);id:UUID;timetable_version_id:UUID;created_at:datetime;updated_at:datetime

class TimetableEntryPage(BaseModel):
 items:list[TimetableEntryResponse];total:int;page:int;page_size:int;pages:int
