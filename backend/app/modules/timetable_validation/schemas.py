from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict
class ValidationRunRequest(BaseModel): academic_term_id:UUID;scope_type:Literal["COLLEGE","DEPARTMENT","PROGRAM","SECTION"];department_id:UUID|None=None;program_id:UUID|None=None;section_id:UUID|None=None
class ValidationIssueResponse(BaseModel): model_config=ConfigDict(from_attributes=True);id:UUID;severity:str;issue_code:str;entity_type:str|None;entity_id:UUID|None;message:str;details:dict|None;created_at:datetime
class ValidationRunSummary(BaseModel): model_config=ConfigDict(from_attributes=True);id:UUID;academic_term_id:UUID;scope_type:str;department_id:UUID|None;program_id:UUID|None;section_id:UUID|None;status:str;total_checks:int;passed_checks:int;failed_checks:int;warning_checks:int;started_at:datetime;completed_at:datetime;created_by:UUID;created_at:datetime
class ValidationRunDetail(ValidationRunSummary): issues:list[ValidationIssueResponse]=[]
class ValidationRunPage(BaseModel): items:list[ValidationRunSummary];total:int;page:int;page_size:int;pages:int
class ValidationIssuePage(BaseModel): items:list[ValidationIssueResponse];total:int;page:int;page_size:int;pages:int
