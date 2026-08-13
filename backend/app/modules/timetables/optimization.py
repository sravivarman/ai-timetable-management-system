"""Centralized Phase 2 optimization profiles and weight validation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SoftConstraintConfig:
 enabled:bool;weight:int;description:str

BALANCED_WEIGHTS={
 "theory_distribution_across_days":SoftConstraintConfig(True,10,"Spread theory periods across working days"),
 "same_course_same_day_excess":SoftConstraintConfig(True,20,"Penalize repeated theory periods on one day"),
 "same_course_adjacent_periods":SoftConstraintConfig(True,8,"Penalize adjacent same-course theory periods"),
 "section_idle_gap":SoftConstraintConfig(True,6,"Reduce section idle gaps"),
 "faculty_idle_gap":SoftConstraintConfig(True,5,"Reduce faculty idle gaps"),
 "faculty_preferred_slot_violation":SoftConstraintConfig(True,8,"Prefer configured faculty slots"),
 "faculty_avoid_slot_violation":SoftConstraintConfig(True,12,"Avoid configured faculty slots"),
 "first_period_fairness":SoftConstraintConfig(True,3,"Distribute first-period duties"),
 "last_period_fairness":SoftConstraintConfig(True,3,"Distribute last-period duties"),
 "faculty_daily_load_imbalance":SoftConstraintConfig(True,5,"Balance faculty daily periods"),
 "section_daily_load_imbalance":SoftConstraintConfig(True,4,"Balance section daily periods"),
 "room_change":SoftConstraintConfig(True,4,"Minimize classroom changes"),
 "laboratory_first_period_preference":SoftConstraintConfig(True,3,"Prefer earlier laboratory sessions"),
 "laboratory_last_period_penalty":SoftConstraintConfig(True,6,"Avoid laboratories ending in period seven"),
 "laboratory_day_spread":SoftConstraintConfig(True,8,"Spread repeated laboratory sessions across days"),
}
PROFILE_DEFAULT_SECONDS={"FAST":15,"BALANCED":60,"QUALITY":180};MAX_WEIGHT=1000

def build_optimization_config(profile="BALANCED",overrides=None):
 if profile not in PROFILE_DEFAULT_SECONDS:raise ValueError("Unknown optimization profile")
 overrides=overrides or {};unknown=set(overrides)-set(BALANCED_WEIGHTS)
 if unknown:raise ValueError("Unknown optimization weights: "+", ".join(sorted(unknown)))
 if any(not isinstance(value,int) or value<0 or value>MAX_WEIGHT for value in overrides.values()):raise ValueError(f"Weights must be integers between 0 and {MAX_WEIGHT}")
 return {name:SoftConstraintConfig(item.enabled,overrides.get(name,item.weight),item.description) for name,item in BALANCED_WEIGHTS.items()}
