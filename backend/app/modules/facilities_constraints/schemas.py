from datetime import date,datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
class AssignmentCreate(BaseModel):
 section_id:UUID;classroom_id:UUID;academic_term_id:UUID;is_primary:bool=True;effective_from:date|None=None;effective_to:date|None=None
 @model_validator(mode="after")
 def dates(self):
  if self.effective_from and self.effective_to and self.effective_from>self.effective_to:raise ValueError("effective_from must be before effective_to")
  return self
class AssignmentUpdate(BaseModel): is_primary:bool|None=None;effective_from:date|None=None;effective_to:date|None=None
class AssignmentRead(AssignmentCreate): model_config=ConfigDict(from_attributes=True);id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
class BlockCreate(BaseModel): laboratory_id:UUID;academic_term_id:UUID;working_day_id:UUID;period_number:int=Field(ge=1,le=7);availability_type:Literal["BLOCKED","ALLOWED"]="BLOCKED";reason:str|None=None
class BlockUpdate(BaseModel): period_number:int|None=Field(default=None,ge=1,le=7);availability_type:Literal["BLOCKED","ALLOWED"]|None=None;reason:str|None=None
class BlockRead(BlockCreate): model_config=ConfigDict(from_attributes=True);id:UUID;is_active:bool;created_at:datetime;updated_at:datetime
