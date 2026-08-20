from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,model_validator
class ValidationRunRequest(BaseModel):
 academic_term_id:UUID;scope_type:Literal["COLLEGE","DEPARTMENT","PROGRAM","SECTION"];department_id:UUID|None=None;program_id:UUID|None=None;section_id:UUID|None=None;scheduling_mode:Literal["WEEKLY","SLOT_BASED"]="WEEKLY";scheduling_slot_id:UUID|None=None
 @model_validator(mode="after")
 def validate_mode_slot(self):
  if self.scheduling_mode=="WEEKLY" and self.scheduling_slot_id is not None:raise ValueError("WEEKLY validation must not specify a Scheduling Slot")
  if self.scheduling_mode=="SLOT_BASED" and self.scheduling_slot_id is None:raise ValueError("SLOT_BASED validation requires a Scheduling Slot")
  return self
class ValidationIssueResponse(BaseModel): model_config=ConfigDict(from_attributes=True);id:UUID;severity:str;issue_code:str;entity_type:str|None;entity_id:UUID|None;message:str;details:dict|None;created_at:datetime
class ValidationRunSummary(BaseModel): model_config=ConfigDict(from_attributes=True);id:UUID;academic_term_id:UUID;scope_type:str;department_id:UUID|None;program_id:UUID|None;section_id:UUID|None;scheduling_mode:str;scheduling_slot_id:UUID|None;status:str;total_checks:int;passed_checks:int;failed_checks:int;warning_checks:int;started_at:datetime;completed_at:datetime;created_by:UUID;created_at:datetime
class ValidationRunDetail(ValidationRunSummary): issues:list[ValidationIssueResponse]=[]
class ValidationRunPage(BaseModel): items:list[ValidationRunSummary];total:int;page:int;page_size:int;pages:int
class ValidationIssuePage(BaseModel): items:list[ValidationIssueResponse];total:int;page:int;page_size:int;pages:int
