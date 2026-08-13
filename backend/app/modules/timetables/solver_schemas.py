from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
from app.modules.timetables.optimization import BALANCED_WEIGHTS,MAX_WEIGHT

class SolveRequest(BaseModel):
 time_limit_seconds:int|None=Field(default=None,ge=1,le=300);random_seed:int=Field(default=1,ge=0);optimization_profile:Literal["FAST","BALANCED","QUALITY"]="BALANCED";weight_overrides:dict[str,int]=Field(default_factory=dict)
 @field_validator("weight_overrides")
 @classmethod
 def validate_weights(cls,value):
  unknown=set(value)-set(BALANCED_WEIGHTS)
  if unknown:raise ValueError("Unknown weight names: "+", ".join(sorted(unknown)))
  if any(weight<0 or weight>MAX_WEIGHT for weight in value.values()):raise ValueError(f"Weights must be between 0 and {MAX_WEIGHT}")
  return value

class SolverQualityResponse(BaseModel):
 solver_run_id:UUID;optimization_profile:str;total_penalty:float;quality_score:float;objective_breakdown:dict[str,float];faculty_daily_loads:dict;faculty_first_last_counts:dict;faculty_idle_gap_counts:dict;section_daily_loads:dict;section_idle_gap_counts:dict;course_day_distribution:dict;laboratory_day_distribution:dict;room_change_counts:dict

class SolverRunResponse(BaseModel):
 model_config=ConfigDict(from_attributes=True);id:UUID;timetable_version_id:UUID;solver_input_snapshot_id:UUID;status:str;started_at:datetime;completed_at:datetime|None;runtime_seconds:float|None;objective_value:float|None;best_bound:float|None;generated_entry_count:int;message:str|None;statistics_json:dict|None;created_by:UUID;created_at:datetime

class SolverRunPage(BaseModel):
 items:list[SolverRunResponse];total:int;page:int;page_size:int;pages:int
