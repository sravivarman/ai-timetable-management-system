from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator
Day=Literal["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]; AvailabilityType=Literal["unavailable","preferred","avoid"]
class AvailabilityBase(BaseModel):
 faculty_id:UUID;academic_term_id:UUID;day_of_week:Day;period_number:int=Field(ge=1,le=7);availability_type:AvailabilityType;reason:str|None=Field(default=None,max_length=1000)
class AvailabilityCreate(AvailabilityBase):pass
class AvailabilityUpdate(BaseModel):
 day_of_week:Day|None=None;period_number:int|None=Field(default=None,ge=1,le=7);availability_type:AvailabilityType|None=None;reason:str|None=None
class AvailabilityRead(AvailabilityBase):
 model_config=ConfigDict(from_attributes=True)
 id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
class AvailabilityBulk(BaseModel): faculty_id:UUID;academic_term_id:UUID;records:list[AvailabilityBase]=Field(min_length=1,max_length=42)
class PolicyBase(BaseModel):
 faculty_id:UUID;academic_term_id:UUID;maximum_periods_per_day:int|None=Field(default=None,ge=1,le=7);avoid_first_period:bool=False;avoid_last_period:bool=False;minimize_idle_gaps:bool=False;fair_first_last_distribution:bool=False;preferred_working_days:list[Day]|None=None
 @field_validator("preferred_working_days")
 @classmethod
 def unique_days(cls,v):
  if v is not None and len(v)!=len(set(v)):raise ValueError("Working days must be unique")
  return v
class PolicyCreate(PolicyBase):pass
class PolicyUpdate(BaseModel):
 maximum_periods_per_day:int|None=Field(default=None,ge=1,le=7);avoid_first_period:bool|None=None;avoid_last_period:bool|None=None;minimize_idle_gaps:bool|None=None;fair_first_last_distribution:bool|None=None;preferred_working_days:list[Day]|None=None
class PolicyRead(PolicyBase):
 model_config=ConfigDict(from_attributes=True)
 id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
class Page(BaseModel):items:list;total:int;page:int;page_size:int;pages:int
