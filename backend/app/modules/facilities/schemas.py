from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
class ClassroomCreate(BaseModel):
 room_number:str=Field(min_length=1,max_length=50);room_name:str|None=None;building_name:str|None=None;floor_number:int|None=None;capacity:int|None=Field(default=None,gt=0);owning_department_id:UUID|None=None;is_primary_classroom:bool=False;is_shareable:bool=True
 @field_validator("room_number")
 @classmethod
 def room(cls,v):return v.strip().upper()
class ClassroomUpdate(ClassroomCreate): pass
class ClassroomResponse(ClassroomCreate):
 model_config=ConfigDict(from_attributes=True);id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
class LaboratoryCreate(BaseModel):
 laboratory_code:str=Field(min_length=1,max_length=50);laboratory_name:str=Field(min_length=1,max_length=255);room_number:str=Field(min_length=1,max_length=50);owning_department_id:UUID;capacity:int|None=Field(default=None,gt=0);concurrent_usage_mode:Literal["EXCLUSIVE","CAPACITY_SHARED"]="EXCLUSIVE";is_shareable_across_departments:bool=True;is_available_all_periods:bool=True;availability_mode:Literal["ALL_PERIODS","EXCEPT_BLOCKED","ONLY_SELECTED"]|None=None
 @field_validator("laboratory_code","room_number")
 @classmethod
 def upper(cls,v):return v.strip().upper()
 @model_validator(mode="after")
 def compatibility(self):
  if self.availability_mode is None:self.availability_mode="ALL_PERIODS" if self.is_available_all_periods else "EXCEPT_BLOCKED"
  self.is_available_all_periods=self.availability_mode=="ALL_PERIODS"
  if self.concurrent_usage_mode=="CAPACITY_SHARED" and self.capacity is None:raise ValueError("capacity is required when concurrent_usage_mode is CAPACITY_SHARED")
  return self
class LaboratoryUpdate(LaboratoryCreate):pass
class LaboratoryResponse(LaboratoryCreate):
 model_config=ConfigDict(from_attributes=True);availability_mode:Literal["ALL_PERIODS","EXCEPT_BLOCKED","ONLY_SELECTED"];id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
