from datetime import datetime,time
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
Day=Literal["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];Type=Literal["FIRST_YEAR","HIGHER_YEAR"];Break=Literal["SHORT_BREAK","LUNCH"]
class WorkingDayCreate(BaseModel):day_name:Day;sequence_number:int=Field(ge=1,le=6);is_working_day:bool=True
class WorkingDayUpdate(BaseModel):day_name:Day|None=None;sequence_number:int|None=Field(default=None,ge=1,le=6);is_working_day:bool|None=None
class WorkingDayRead(WorkingDayCreate):model_config=ConfigDict(from_attributes=True);id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
class PeriodBase(BaseModel):
 schedule_type:Type;period_number:int=Field(ge=1,le=7);start_time:time;end_time:time;duration_minutes:int=Field(gt=0);is_instructional:bool=True;break_type:Break|None=None;sequence_number:int=Field(ge=1)
 @model_validator(mode="after")
 def timing(self):
  minutes=(self.end_time.hour*60+self.end_time.minute)-(self.start_time.hour*60+self.start_time.minute)
  if minutes<=0 or minutes!=self.duration_minutes:raise ValueError("duration_minutes must match start_time and end_time")
  return self
class PeriodCreate(PeriodBase):pass
class PeriodUpdate(BaseModel):start_time:time|None=None;end_time:time|None=None;duration_minutes:int|None=Field(default=None,gt=0);is_instructional:bool|None=None;break_type:Break|None=None;sequence_number:int|None=Field(default=None,ge=1)
class PeriodRead(PeriodBase):model_config=ConfigDict(from_attributes=True);id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
