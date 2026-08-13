"""Deterministic CP-SAT timetable solver with hard and weighted soft constraints."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from itertools import product
from time import perf_counter
from uuid import UUID
from fastapi import HTTPException
from ortools.sat.python import cp_model
from sqlalchemy import delete,select
from app.modules.combined_teaching.models import CombinedTeachingEvent
from app.modules.timetable_validation.models import ValidationRun
from app.modules.resource_availability.service import snapshot_resource_is_available
from app.modules.timetables.models import SolverRun,Timetable,TimetableEntry,TimetableEntryAudit,TimetableVersion
from app.modules.timetables.capacity import entry_capacity_demand
from app.modules.timetables.service import solver_input_builder
from app.modules.timetables.optimization import PROFILE_DEFAULT_SECONDS,build_optimization_config

IMMUTABLE={"APPROVED","PUBLISHED","ARCHIVED"}

class TimetableSolverService:
 def _eligible(self,db,version_id):
  version=db.scalar(select(TimetableVersion).where(TimetableVersion.id==version_id))
  if not version:raise HTTPException(404,"Timetable version not found")
  timetable=db.scalar(select(Timetable).where(Timetable.id==version.timetable_id))
  if not timetable:raise HTTPException(404,"Timetable not found")
  if not version.is_active:raise HTTPException(409,"Timetable version is inactive")
  if version.is_locked:raise HTTPException(409,"Timetable version is locked")
  if timetable.status in IMMUTABLE:raise HTTPException(409,"Timetable is immutable")
  if version.solver_status=="RUNNING":raise HTTPException(409,"Solver is already running for this version")
  if version.solver_status=="STALE":raise HTTPException(409,"Solver input is stale; rebuild it before solving")
  validation=db.scalar(select(ValidationRun).where(ValidationRun.id==version.validation_run_id))
  if not validation or validation.status not in {"PASSED","WARNING"}:raise HTTPException(422,"Validation run must have PASSED or WARNING status")
  snapshot=solver_input_builder.latest(db,version_id)
  if solver_input_builder.current_hash(db,version_id)!=snapshot.input_hash:raise HTTPException(409,"Solver input snapshot is stale; rebuild it before solving")
  return version,timetable,snapshot

 def solve(self,db,version_id,user_id,time_limit_seconds=None,random_seed=1,optimization_profile="BALANCED",weight_overrides=None):
  version,timetable,snapshot=self._eligible(db,version_id);now=datetime.now(timezone.utc)
  try:optimization_config=build_optimization_config(optimization_profile,weight_overrides)
  except ValueError as error:raise HTTPException(422,str(error)) from error
  effective_time_limit=time_limit_seconds or PROFILE_DEFAULT_SECONDS[optimization_profile]
  run=SolverRun(timetable_version_id=version.id,solver_input_snapshot_id=snapshot.id,status="RUNNING",started_at=now,generated_entry_count=0,created_by=user_id,created_at=now)
  version.solver_status="RUNNING";db.add(run);db.commit();db.refresh(run)
  started=perf_counter()
  try:
   result=self._solve_snapshot(db,snapshot.snapshot_json,version.id,effective_time_limit,random_seed,optimization_config,optimization_profile)
   elapsed=perf_counter()-started;completed=datetime.now(timezone.utc)
   run=db.get(SolverRun,run.id);version=db.get(TimetableVersion,version.id);timetable=db.get(Timetable,timetable.id)
   run.status=result["status"];run.completed_at=completed;run.runtime_seconds=elapsed;run.objective_value=result.get("objective_value");run.best_bound=result.get("best_bound");run.message=result.get("message");run.statistics_json=result["statistics"]
   if result["status"] in {"FEASIBLE","OPTIMAL"}:
    db.execute(delete(CombinedTeachingEvent).where(CombinedTeachingEvent.timetable_version_id==version.id,CombinedTeachingEvent.is_manual.is_(False),CombinedTeachingEvent.is_locked.is_(False)))
    db.execute(delete(TimetableEntry).where(TimetableEntry.timetable_version_id==version.id,TimetableEntry.is_manual.is_(False),TimetableEntry.is_locked.is_(False)))
    created=[]
    combined_events={}
    for values in result["entries"]:
     values=dict(values);group_id=values.pop("_combined_group_id",None);event_key=values.pop("_combined_event_key",None)
     if group_id:
      event=combined_events.get(event_key)
      if not event:
       event=CombinedTeachingEvent(timetable_version_id=version.id,combined_teaching_group_id=group_id,working_day_id=values["working_day_id"],period_number=values["period_number"],session_length=values["session_length"],faculty_id=values["faculty_id"],classroom_id=values.get("classroom_id"),laboratory_id=values.get("laboratory_id"),is_manual=False,is_locked=False,created_at=completed,updated_at=completed);db.add(event);db.flush();combined_events[event_key]=event
      values["combined_teaching_event_id"]=event.id
     entry=TimetableEntry(timetable_version_id=version.id,**values,is_manual=False,is_locked=False,created_at=completed,updated_at=completed);db.add(entry);created.append(entry)
    db.flush()
    for entry in created:
     values={field:(str(value) if isinstance(value,UUID) else value) for field,value in {"course_offering_id":entry.course_offering_id,"section_id":entry.section_id,"faculty_id":entry.faculty_id,"laboratory_faculty_allocation_id":entry.laboratory_faculty_allocation_id,"classroom_id":entry.classroom_id,"laboratory_id":entry.laboratory_id,"student_batch_id":entry.student_batch_id,"laboratory_rotation_block_id":entry.laboratory_rotation_block_id,"laboratory_rotation_assignment_id":entry.laboratory_rotation_assignment_id,"combined_teaching_event_id":entry.combined_teaching_event_id,"working_day_id":entry.working_day_id,"period_number":entry.period_number,"session_length":entry.session_length,"entry_type":entry.entry_type,"is_manual":entry.is_manual,"is_locked":entry.is_locked}.items()};db.add(TimetableEntryAudit(timetable_entry_id=entry.id,timetable_version_id=version.id,action_type="GENERATED",old_values_json=None,new_values_json=values,performed_by=user_id,created_at=completed))
    run.generated_entry_count=len(created);version.solver_status=result["status"];timetable.status="GENERATED"
   else:version.solver_status=result["status"]
   db.commit();db.refresh(run);return run
  except Exception as error:
   db.rollback();run=db.get(SolverRun,run.id);version=db.get(TimetableVersion,version.id);completed=datetime.now(timezone.utc);run.status="FAILED";run.completed_at=completed;run.runtime_seconds=perf_counter()-started;run.message=str(error)[:1000];run.statistics_json={"exception_type":type(error).__name__};version.solver_status="FAILED";db.commit();db.refresh(run);return run

 def _solve_snapshot(self,db,snapshot,version_id,time_limit,seed,optimization_config=None,optimization_profile="BALANCED"):
  optimization_config=optimization_config or build_optimization_config(optimization_profile)
  offerings={item["id"]:item for item in snapshot["course_offerings"]}
  sections={item["id"]:item for item in snapshot["sections"]};days=sorted(snapshot["working_days"],key=lambda item:(item["sequence_number"],item["id"]));day_names={item["id"]:item["day_name"] for item in days}
  schedule_type=snapshot["metadata"].get("schedule_type","HIGHER_YEAR");timings=sorted((item for item in snapshot["period_timings"] if item["schedule_type"]==schedule_type),key=lambda item:(item["sequence_number"],item["id"]));lunch=next((item["sequence_number"] for item in timings if not item["is_instructional"] and item["break_type"]=="LUNCH"),None);positions={item["period_number"]:item["sequence_number"] for item in timings if item["is_instructional"]}
  primary={item["section_id"]:item["classroom_id"] for item in snapshot["primary_classroom_assignments"]}
  theory_alloc=defaultdict(list)
  for item in snapshot["theory_faculty_allocations"]:theory_alloc[item["course_offering_id"]].append(item)
  lab_alloc=defaultdict(list)
  for item in snapshot["laboratory_faculty_allocations"]:lab_alloc[item["course_offering_id"]].append(item)
  mandatory_rules=defaultdict(set)
  for item in snapshot["laboratory_session_faculty_rules"]:
   if item["is_mandatory_for_session"]:mandatory_rules[item["laboratory_faculty_allocation_id"]].add(item["session_number"])
  batches=defaultdict(list)
  for item in snapshot["student_batches"]:batches[item["section_id"]].append(item)
  for values in batches.values():values.sort(key=lambda item:(item["sequence_number"],item["id"]))
  batch_by_id={item["id"]:item for item in snapshot["student_batches"]}
  laboratories={item["id"]:{**item,"concurrent_usage_mode":item.get("concurrent_usage_mode","EXCLUSIVE")} for item in snapshot.get("laboratories",[])}
  configurations={item["id"]:item for item in snapshot["laboratory_batch_configurations"]};configuration_by_offering={item["course_offering_id"]:item for item in configurations.values()}
  rotation_blocks={item["id"]:item for item in snapshot.get("laboratory_rotation_blocks",[])}
  assignments_by_block=defaultdict(list)
  for item in snapshot["laboratory_rotation_assignments"]:
   if item.get("rotation_block_id"):assignments_by_block[item["rotation_block_id"]].append(item)
  rotation_offering_ids={item["course_offering_id"] for item in snapshot["laboratory_rotation_assignments"]}
  faculty_by_id={item["id"]:item for item in snapshot["faculty"]};policy_by_faculty={item["faculty_id"]:item for item in snapshot["faculty_scheduling_policies"]}
  preferred={(item["faculty_id"],item["day_of_week"],item["period_number"]) for item in snapshot["faculty_availability"] if item["availability_type"]=="preferred"}
  avoided={(item["faculty_id"],item["day_of_week"],item["period_number"]) for item in snapshot["faculty_availability"] if item["availability_type"]=="avoid"}
  faculty_with_preferences={item[0] for item in preferred}
  resource_modes={(item["resource_type"],item["resource_id"]):item["availability_mode"] for item in snapshot.get("resource_availability_profiles",[]) if item.get("id")}
  resource_slots={(item["resource_type"],item["resource_id"],item["working_day_id"],item["period_number"],item["availability_type"]) for item in snapshot.get("resource_availability_slots",[])}
  # Old snapshots remain executable after the generic engine is introduced.
  for item in snapshot.get("laboratory_availability_blocks",[]):
   resource_id=item.get("resource_id") or item.get("laboratory_id");resource_slots.add(("LABORATORY",resource_id,item["working_day_id"],item["period_number"],item.get("availability_type","BLOCKED")))
  for laboratory in snapshot.get("laboratories",[]):resource_modes.setdefault(("LABORATORY",laboratory["id"]),laboratory.get("availability_mode") or ("ALL_PERIODS" if laboratory.get("is_available_all_periods",True) else "EXCEPT_BLOCKED"))
  day_ids={item["day_name"]:item["id"] for item in snapshot["working_days"]}
  for item in snapshot["faculty_availability"]:
   if item["availability_type"]=="unavailable" and item["day_of_week"] in day_ids:
    resource_modes.setdefault(("FACULTY",item["faculty_id"]),"EXCEPT_BLOCKED");resource_slots.add(("FACULTY",item["faculty_id"],day_ids[item["day_of_week"]],item["period_number"],"BLOCKED"))
  allocation_faculty={item["id"]:item["faculty_id"] for item in snapshot["laboratory_faculty_allocations"]}
  fixed={item["id"]:item for item in snapshot["locked_entries"]}
  for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id,TimetableEntry.is_manual.is_(True))):
   fixed[str(entry.id)]={key:(str(value) if isinstance(value,UUID) else value) for key,value in {"id":entry.id,"course_offering_id":entry.course_offering_id,"section_id":entry.section_id,"faculty_id":entry.faculty_id,"laboratory_faculty_allocation_id":entry.laboratory_faculty_allocation_id,"classroom_id":entry.classroom_id,"laboratory_id":entry.laboratory_id,"student_batch_id":entry.student_batch_id,"laboratory_rotation_block_id":entry.laboratory_rotation_block_id,"laboratory_rotation_assignment_id":entry.laboratory_rotation_assignment_id,"combined_teaching_event_id":entry.combined_teaching_event_id,"working_day_id":entry.working_day_id,"period_number":entry.period_number,"session_length":entry.session_length,"entry_type":entry.entry_type,"capacity_demand":entry_capacity_demand(db,entry)}.items()}
  rotation_assignment_by_id={item["id"]:item for item in snapshot["laboratory_rotation_assignments"]}
  fixed_rotation_blocks={item.get("laboratory_rotation_block_id") for item in fixed.values() if item.get("laboratory_rotation_block_id")}
  combined_groups=snapshot.get("combined_teaching_groups",[]);combined_offering_ids={offering_id for group in combined_groups for offering_id in group["course_offering_ids"]}
  fixed_combined_counts=Counter(item.get("combined_teaching_event_id") for item in fixed.values() if item.get("combined_teaching_event_id"))

  units=[];input_errors=[]
  for group in sorted(combined_groups,key=lambda item:(item["group_code"],item["id"])):
   group_offerings=[offerings.get(value) for value in group["course_offering_ids"]]
   if len(group_offerings)<2 or any(value is None for value in group_offerings):input_errors.append(f"Incomplete combined teaching group {group['group_code']}");continue
   already=len({item.get("combined_teaching_event_id") for item in fixed.values() if item.get("combined_teaching_event_id") and item["course_offering_id"] in group["course_offering_ids"]})
   venue=group["venue_requirement"]
   if venue=="CLASSROOM_ONLY":venue_options=[{"classroom_id":value,"laboratory_id":None} for value in group.get("eligible_classroom_ids",[])]
   elif venue=="LABORATORY_ONLY":venue_options=[{"classroom_id":None,"laboratory_id":value} for value in group.get("eligible_laboratory_ids",[])]
   elif venue=="CLASSROOM_OR_LABORATORY":venue_options=[{"classroom_id":value,"laboratory_id":None} for value in group.get("eligible_classroom_ids",[])]+[{"classroom_id":None,"laboratory_id":value} for value in group.get("eligible_laboratory_ids",[])]
   else:venue_options=[{"classroom_id":None,"laboratory_id":None}]
   if not venue_options:input_errors.append(f"No eligible venue for combined group {group['group_code']}");continue
   children=[{"offering":offering,"section_id":offering["section_id"]} for offering in group_offerings]
   for session_number in range(already+1,group["sessions_per_week"]+1):
    units.append({"offering":group_offerings[0],"section_id":group["section_ids"][0],"section_ids":group["section_ids"],"entry_type":group_offerings[0]["course_type"],"length":group["session_duration"],"faculty_options":[[group["faculty_id"]]],"faculty_id":group["faculty_id"],"lab_allocation_id":None,"venue_options":venue_options,"classroom_id":group.get("preferred_classroom_id"),"laboratory_id":group.get("preferred_laboratory_id"),"laboratory_ids":[],"batch_id":None,"batch_ids":[],"capacity_demand":group["combined_strength"],"combined_group_id":group["id"],"children":children,"session_number":session_number})
  # A rotation block is one CP-SAT decision. Its child laboratory entries are
  # expanded only after the solver chooses the shared day and starting period.
  for block in sorted(rotation_blocks.values(),key=lambda item:(item["rotation_group_id"],item["block_number"],item["id"])):
   if block["id"] in fixed_rotation_blocks:
    expected={item["id"] for item in assignments_by_block[block["id"]]};actual={item.get("laboratory_rotation_assignment_id") for item in fixed.values() if item.get("laboratory_rotation_block_id")==block["id"]}
    if expected!=actual:input_errors.append(f"Incomplete locked synchronized rotation block {block['block_number']}")
    continue
   children=[]
   for assignment in sorted(assignments_by_block[block["id"]],key=lambda item:(item["rotation_position"],item["id"])):
    offering=offerings.get(assignment["course_offering_id"])
    if not offering:continue
    faculty_ids=[assignment.get("main_faculty_id"),*(assignment.get("supporting_faculty_ids") or [])]
    faculty_ids=[faculty for faculty in faculty_ids if faculty]
    if offering["course_type"]=="LABORATORY":
     allocation=next((item for item in lab_alloc[offering["id"]] if item["role_type"]=="MAIN" and item["faculty_id"]==assignment.get("main_faculty_id")),None)
    else:
     allocation=next((item for item in theory_alloc[offering["id"]] if item["faculty_id"]==assignment.get("main_faculty_id")),None)
    candidate_laboratories=[assignment["laboratory_id"]] if assignment.get("laboratory_id") else list(offering.get("eligible_laboratory_ids") or [])
    children.append({"assignment_id":assignment["id"],"offering":offering,"batch_id":assignment["batch_id"],"capacity_demand":batch_by_id[assignment["batch_id"]]["student_count"],"laboratory_id":assignment.get("laboratory_id"),"candidate_laboratory_ids":candidate_laboratories,"faculty_id":assignment.get("main_faculty_id"),"faculty_ids":faculty_ids,"lab_allocation_id":allocation["id"] if offering["course_type"]=="LABORATORY" and allocation else None,"length":assignment.get("session_duration"),"entry_type":offering["course_type"]})
   if len(children)<2 or len({child["batch_id"] for child in children})!=len(children) or any(not child["candidate_laboratory_ids"] for child in children) or len({child["length"] for child in children})!=1:
    input_errors.append(f"Invalid synchronized rotation block {block['block_number']}");continue
   length=children[0]["length"]
   if length not in (2,3):input_errors.append(f"Invalid synchronized rotation duration for block {block['block_number']}");continue
   venue_options=[]
   for laboratory_choice in product(*(child["candidate_laboratory_ids"] for child in children)):
    valid=True
    for laboratory_id in set(laboratory_choice):
     uses=[child for child,chosen in zip(children,laboratory_choice) if chosen==laboratory_id];laboratory=laboratories.get(laboratory_id,{})
     if len(uses)>1 and (laboratory.get("concurrent_usage_mode")!="CAPACITY_SHARED" or sum(item["capacity_demand"] for item in uses)>int(laboratory.get("capacity") or 0)):valid=False
    if valid:venue_options.append({"classroom_id":None,"laboratory_id":None,"laboratory_ids":list(laboratory_choice)})
   if not venue_options:input_errors.append(f"No capacity-feasible eligible laboratories for synchronized rotation block {block['block_number']}");continue
   units.append({"offering":children[0]["offering"],"section_id":children[0]["offering"]["section_id"],"section_ids":[children[0]["offering"]["section_id"]],"entry_type":"LABORATORY","length":length,"faculty_options":[sorted({faculty for child in children for faculty in child["faculty_ids"]})],"faculty_id":children[0]["faculty_id"],"lab_allocation_id":children[0]["lab_allocation_id"],"venue_options":venue_options,"classroom_id":None,"laboratory_id":None,"laboratory_ids":venue_options[0]["laboratory_ids"],"batch_id":None,"batch_ids":[child["batch_id"] for child in children],"rotation_block_id":block["id"],"children":children})
  for offering in sorted(offerings.values(),key=lambda item:(item["section_id"],item["course_code"],item["id"])):
   if not offering["is_mandatory"]:continue
   existing=[item for item in fixed.values() if item["course_offering_id"]==offering["id"]]
   if offering["id"] in rotation_offering_ids or offering["id"] in combined_offering_ids:continue
   duration=offering.get("session_duration") or offering.get("lab_session_duration") or 1
   sessions=offering.get("sessions_per_week") or offering.get("lab_sessions_per_week")
   count=offering.get("effective_group_count") or offering.get("effective_lab_group_count") or 1
   grouped=offering.get("grouping_mode")=="GROUPED" or (not offering.get("grouping_mode") and offering["course_type"]=="LABORATORY" and count>1)
   if not sessions or duration<1:input_errors.append(f"Invalid session configuration for {offering['course_code']}");continue
   selected_batches=batches[offering["section_id"]][:count] if grouped else [None]
   if grouped and len(selected_batches)!=count:input_errors.append(f"Incomplete student groups for {offering['course_code']}");continue
   primary_room=primary.get(offering["section_id"]);venue=offering.get("venue_requirement") or ("LABORATORY_ONLY" if offering["course_type"]=="LABORATORY" else "CLASSROOM_ONLY")
   classroom_ids=list(dict.fromkeys([value for value in [primary_room,*(offering.get("eligible_classroom_ids") or [])] if value]))
   laboratory_ids=list(dict.fromkeys(offering.get("eligible_laboratory_ids") or []))
   if venue=="CLASSROOM_ONLY":venue_options=[{"classroom_id":value,"laboratory_id":None} for value in classroom_ids]
   elif venue=="LABORATORY_ONLY":venue_options=[{"classroom_id":None,"laboratory_id":value} for value in laboratory_ids]
   elif venue=="CLASSROOM_OR_LABORATORY":venue_options=[{"classroom_id":value,"laboratory_id":None} for value in classroom_ids]+[{"classroom_id":None,"laboratory_id":value} for value in laboratory_ids]
   else:venue_options=[{"classroom_id":None,"laboratory_id":None}]
   if not venue_options:input_errors.append(f"No eligible venue for {offering['course_code']}");continue
   lab_course=offering["course_type"]=="LABORATORY"
   if lab_course:
    mains=sorted((item for item in lab_alloc[offering["id"]] if item["role_type"]=="MAIN"),key=lambda item:(item["faculty_id"],item["id"]))
    if not mains:input_errors.append(f"Missing MAIN faculty for {offering['course_code']}");continue
    main=mains[0]
   else:
    allocations=sorted(theory_alloc[offering["id"]],key=lambda item:(item["faculty_id"],item["id"]));main=allocations[0] if allocations else None
    if offering["course_type"] in {"THEORY","CDC","PRACTICAL"} and not main:input_errors.append(f"Missing faculty for {offering['course_code']}");continue
   supporting_groups=defaultdict(list)
   if lab_course:
    for supporting in sorted((item for item in lab_alloc[offering["id"]] if item["role_type"]=="SUPPORTING"),key=lambda item:(item.get("alternative_group_code") or item["id"],item["faculty_id"],item["id"])):supporting_groups[supporting.get("alternative_group_code") or supporting["id"]].append(supporting)
   for batch in selected_batches:
    batch_id=batch["id"] if batch else None;already=sum(1 for item in existing if item.get("student_batch_id")==batch_id)
    for session_number in range(already+1,sessions+1):
     support_options=[]
     for group in supporting_groups.values():
      eligible=[];group_required=False
      for supporting in group:
       required_sessions=set(mandatory_rules[supporting["id"]]);required_sessions.update(range(1,(supporting.get("minimum_sessions_per_week") or 0)+1));maximum=supporting.get("maximum_sessions_per_week")
       if maximum is not None and len(required_sessions)>maximum:input_errors.append(f"Invalid SUPPORTING faculty session limits for {offering['course_code']}")
       group_required=group_required or session_number in required_sessions;required=supporting.get("required_with_main_faculty_id")
       if not required or required==main["faculty_id"]:eligible.append(supporting)
      if group_required:
       if not eligible:input_errors.append(f"No eligible SUPPORTING faculty for {offering['course_code']}")
       else:support_options.append(eligible)
     combinations=product(*support_options) if support_options else [()]
     faculty_options=[sorted({*([main["faculty_id"]] if main else []),*(item["faculty_id"] for item in selected)}) for selected in combinations]
     demand=batch["student_count"] if batch else offering["full_section_capacity_demand"]
     units.append({"offering":offering,"section_id":offering["section_id"],"section_ids":[offering["section_id"]],"entry_type":offering["course_type"],"length":duration,"faculty_options":faculty_options,"faculty_id":main["faculty_id"] if main else None,"lab_allocation_id":main["id"] if lab_course else None,"venue_options":venue_options,"classroom_id":venue_options[0]["classroom_id"],"laboratory_id":venue_options[0]["laboratory_id"],"laboratory_ids":[venue_options[0]["laboratory_id"]] if venue_options[0]["laboratory_id"] else [],"batch_id":batch_id,"batch_ids":[batch_id] if batch_id else [],"capacity_demand":demand,"session_number":session_number})

  model=cp_model.CpModel();assignments=[];resource_vars=defaultdict(list);laboratory_terms=defaultdict(list);section_vars=defaultdict(lambda:defaultdict(list));course_day=defaultdict(list);lab_day=defaultdict(list);faculty_day=defaultdict(list)
  if input_errors:model.add(0==1)
  fixed_resources=defaultdict(int);fixed_laboratory_demand=defaultdict(int);fixed_section=defaultdict(lambda:defaultdict(int));fixed_faculty_day=defaultdict(int);fixed_course_day=defaultdict(list);fixed_lab_day=defaultdict(int)
  fixed_section_units=set()
  seen_fixed_resources=set()
  for item in fixed.values():
   faculty_id=item.get("faculty_id") or allocation_faculty.get(item.get("laboratory_faculty_allocation_id"));rotation_assignment=rotation_assignment_by_id.get(item.get("laboratory_rotation_assignment_id"),{});fixed_faculties={value for value in [faculty_id,rotation_assignment.get("main_faculty_id"),*(rotation_assignment.get("supporting_faculty_ids") or [])] if value};occupied=range(item["period_number"],item["period_number"]+item["session_length"])
   shared_key=item.get("combined_teaching_event_id")
   for period in occupied:
    resource_key=(shared_key,item["working_day_id"],period)
    first_resource=not shared_key or resource_key not in seen_fixed_resources
    if first_resource:
     for faculty in fixed_faculties:fixed_resources[("faculty",faculty,item["working_day_id"],period)]+=1
     for kind,value in (("classroom",item.get("classroom_id")),("batch",item.get("student_batch_id"))):
      if value:fixed_resources[(kind,value,item["working_day_id"],period)]+=1
     laboratory_id=item.get("laboratory_id")
     if laboratory_id:
      key=("laboratory",laboratory_id,item["working_day_id"],period);fixed_resources[key]+=1;fixed_laboratory_demand[key]+=int(item.get("capacity_demand") or sections.get(item["section_id"],{}).get("student_strength") or 0)
     if shared_key:seen_fixed_resources.add(resource_key)
    group=item.get("student_batch_id") or "__FULL__";fixed_section[(item["section_id"],item["working_day_id"],period)][group]+=1
    if first_resource:
     for faculty in fixed_faculties:fixed_faculty_day[(faculty,item["working_day_id"])]+=1
   fixed_course_day[(item["course_offering_id"],item["working_day_id"])].append(item["period_number"])
   if item["entry_type"]=="LABORATORY":fixed_lab_day[(item["section_id"],item["working_day_id"])]+=1

  for index,unit in enumerate(units):
   variables=[]
   for option_index,faculty_ids in enumerate(unit["faculty_options"]):
    venue_options=unit.get("venue_options") or [{"classroom_id":unit.get("classroom_id"),"laboratory_id":unit.get("laboratory_id")}]
    for venue_index,venue_option in enumerate(venue_options):
     selected_classroom=venue_option.get("classroom_id");selected_laboratory=venue_option.get("laboratory_id")
     selected_laboratories=venue_option.get("laboratory_ids",unit.get("laboratory_ids",[])) if unit.get("rotation_block_id") else ([selected_laboratory] if selected_laboratory else [])
     for day in days:
      for start in range(1,8-unit["length"]+1):
       end=start+unit["length"]-1
       if any(period not in positions for period in range(start,end+1)):continue
       if lunch is not None and positions[start]<lunch<positions[end]:continue
       occupied=tuple(range(start,end+1))
       if any(not snapshot_resource_is_available("FACULTY",faculty,resource_modes,resource_slots,day["id"],period) for faculty in faculty_ids for period in occupied):continue
       if any(not snapshot_resource_is_available("LABORATORY",laboratory_id,resource_modes,resource_slots,day["id"],period) for laboratory_id in selected_laboratories if laboratory_id for period in occupied):continue
       if selected_classroom and any(not snapshot_resource_is_available("CLASSROOM",selected_classroom,resource_modes,resource_slots,day["id"],period) for period in occupied):continue
       laboratory_demands=defaultdict(int)
       if unit.get("rotation_block_id"):
        for child,laboratory_id in zip(unit["children"],selected_laboratories):laboratory_demands[laboratory_id]+=int(child["capacity_demand"])
       elif selected_laboratory:laboratory_demands[selected_laboratory]=int(unit["capacity_demand"])
       if any(laboratories.get(laboratory_id,{}).get("capacity") is not None and demand>int(laboratories[laboratory_id]["capacity"]) for laboratory_id,demand in laboratory_demands.items()):continue
       variable=model.new_bool_var(f"u{index}_o{option_index}_v{venue_index}_{day['sequence_number']}_{start}");variables.append(variable);record={"var":variable,"unit":unit,"faculty_ids":faculty_ids,"support_option_index":option_index,"day_id":day["id"],"start":start,"occupied":occupied,"classroom_id":selected_classroom,"laboratory_id":selected_laboratory,"laboratory_ids":selected_laboratories,"laboratory_demands":dict(laboratory_demands)};assignments.append(record)
       for period in occupied:
        for faculty in faculty_ids:resource_vars[("faculty",faculty,day["id"],period)].append(variable)
        if selected_classroom:resource_vars[("classroom",selected_classroom,day["id"],period)].append(variable)
        for laboratory_id,demand in laboratory_demands.items():laboratory_terms[("laboratory",laboratory_id,day["id"],period)].append((variable,demand))
        for batch_id in unit.get("batch_ids",[]):resource_vars[("batch",batch_id,day["id"],period)].append(variable)
        for section_id in unit.get("section_ids",[unit["section_id"]]):section_vars[(section_id,day["id"],period)][unit["batch_id"] or "__FULL__"].append(variable)
       for child in unit.get("children",[]) if unit.get("combined_group_id") else [{"offering":unit["offering"]}]:course_day[(child["offering"]["id"],day["id"])].append((variable,start))
       if unit["entry_type"]=="LABORATORY":lab_day[(unit["section_id"],day["id"])].append(variable)
       for faculty in faculty_ids:faculty_day[(faculty,day["id"])].append((variable,unit["length"]))
   if variables:model.add_exactly_one(variables)
   else:model.add(0==1)

  if any(count>1 for key,count in fixed_resources.items() if key[0]!="laboratory"):model.add(0==1)
  for key,variables in resource_vars.items():model.add(sum(variables)<=max(0,1-fixed_resources[key]))
  laboratory_keys=set(laboratory_terms)|{key for key in fixed_resources if key[0]=="laboratory"}
  for key in laboratory_keys:
   laboratory=laboratories.get(key[1],{});mode=laboratory.get("concurrent_usage_mode","EXCLUSIVE");terms=laboratory_terms.get(key,[])
   if mode=="CAPACITY_SHARED":
    capacity=int(laboratory.get("capacity") or 0)
    if capacity<=0 or fixed_laboratory_demand[key]>capacity:model.add(0==1)
    else:model.add(sum(variable*demand for variable,demand in terms)<=capacity-fixed_laboratory_demand[key])
   else:
    if fixed_resources[key]>1:model.add(0==1)
    model.add(sum(variable for variable,_ in terms)<=max(0,1-fixed_resources[key]))
  for key,groups in section_vars.items():
   fixed_groups=fixed_section[key];full=groups.get("__FULL__",[]);fixed_full=fixed_groups.get("__FULL__",0)
   if fixed_full>1:model.add(0==1)
   model.add(sum(full)<=max(0,1-fixed_full))
   batch_ids=(set(groups)-{"__FULL__"})|(set(fixed_groups)-{"__FULL__"})
   for batch_id in batch_ids:model.add(sum(full+groups.get(batch_id,[]))<=max(0,1-fixed_full-fixed_groups.get(batch_id,0)))
  for (faculty,day_id),values in faculty_day.items():
   limits=[faculty_by_id.get(faculty,{}).get("maximum_periods_per_day"),policy_by_faculty.get(faculty,{}).get("maximum_periods_per_day")];limits=[limit for limit in limits if limit]
   if limits:model.add(sum(variable*length for variable,length in values)<=max(0,min(limits)-fixed_faculty_day[(faculty,day_id)]))
  for key,values in course_day.items():
   offering=offerings[key[0]]
   if offering["course_type"]=="THEORY":
    fixed_periods=fixed_course_day[key];model.add(sum(variable for variable,_ in values)<=max(0,2-len(fixed_periods)))
    if not offering.get("allows_same_course_double_period"):
     for start in range(1,7):model.add(sum(variable for variable,value_start in values if value_start in (start,start+1))<=1)
     for fixed_start in fixed_periods:
      for variable,value_start in values:
       if abs(value_start-fixed_start)==1:model.add(variable==0)
  for key,values in lab_day.items():model.add(sum(values)<=max(0,1-fixed_lab_day[key]))

  # Phase 2: build one integer weighted objective while retaining every hard
  # constraint above. Expressions are grouped so the persisted explanation is
  # computed from exactly the same terms that CP-SAT minimizes.
  hard_constraint_count=len(model.Proto().constraints);penalty_terms=defaultdict(list)
  def add_penalty(family,expression,weight_name,multiplier=1):
   config=optimization_config[weight_name]
   if config.enabled and config.weight:penalty_terms[family].append((expression,config.weight*multiplier))

  occupancy_sources=defaultdict(list);fixed_occupancy=set()
  for record in assignments:
   for period in record["occupied"]:
    for section_id in record["unit"].get("section_ids",[record["unit"]["section_id"]]):occupancy_sources[("section",section_id,record["day_id"],period)].append(record["var"])
    for faculty in record["faculty_ids"]:occupancy_sources[("faculty",faculty,record["day_id"],period)].append(record["var"])
  for item in fixed.values():
   faculty_id=item.get("faculty_id") or allocation_faculty.get(item.get("laboratory_faculty_allocation_id"));rotation_assignment=rotation_assignment_by_id.get(item.get("laboratory_rotation_assignment_id"),{});fixed_faculties={value for value in [faculty_id,rotation_assignment.get("main_faculty_id"),*(rotation_assignment.get("supporting_faculty_ids") or [])] if value}
   for period in range(item["period_number"],item["period_number"]+item["session_length"]):
    fixed_occupancy.add(("section",item["section_id"],item["working_day_id"],period))
    for faculty in fixed_faculties:fixed_occupancy.add(("faculty",faculty,item["working_day_id"],period))

  relevant={"section":sorted({section_id for record in assignments for section_id in record["unit"].get("section_ids",[record["unit"]["section_id"]])}|{item["section_id"] for item in fixed.values()}),"faculty":sorted({faculty for record in assignments for faculty in record["faculty_ids"]}|{key[1] for key in fixed_occupancy if key[0]=="faculty"})}
  occupancy={}
  for kind,identifiers in relevant.items():
   for identifier in identifiers:
    for day in days:
     for period in range(1,8):
      key=(kind,identifier,day["id"],period);variable=model.new_bool_var(f"occ_{kind}_{identifier}_{day['sequence_number']}_{period}");occupancy[key]=variable
      if key in fixed_occupancy:model.add(variable==1)
      elif occupancy_sources[key]:model.add_max_equality(variable,occupancy_sources[key])
      else:model.add(variable==0)

  # Empty instructional slots bounded by work on both sides are genuine gaps;
  # lunch and short breaks do not have period numbers and are therefore absent.
  for kind,identifiers in relevant.items():
   family="section_gap_penalty" if kind=="section" else "faculty_gap_penalty";weight="section_idle_gap" if kind=="section" else "faculty_idle_gap"
   for identifier in identifiers:
    for day in days:
     for period in range(2,7):
      before=model.new_bool_var(f"before_{kind}_{identifier}_{day['sequence_number']}_{period}");after=model.new_bool_var(f"after_{kind}_{identifier}_{day['sequence_number']}_{period}");gap=model.new_bool_var(f"gap_{kind}_{identifier}_{day['sequence_number']}_{period}")
      model.add_max_equality(before,[occupancy[(kind,identifier,day["id"],value)] for value in range(1,period)])
      model.add_max_equality(after,[occupancy[(kind,identifier,day["id"],value)] for value in range(period+1,8)])
      current=occupancy[(kind,identifier,day["id"],period)];model.add(gap<=before);model.add(gap<=after);model.add(gap+current<=1);model.add(gap>=before+after-current-1);add_penalty(family,gap,weight)

  # Daily load spread and first/last-period fairness use period occupancy, so
  # multi-period laboratories and locked entries are accounted for correctly.
  for kind,identifiers in relevant.items():
   for identifier in identifiers:
    loads=[]
    for day in days:
     load=model.new_int_var(0,7,f"load_{kind}_{identifier}_{day['sequence_number']}");model.add(load==sum(occupancy[(kind,identifier,day["id"],period)] for period in range(1,8)));loads.append(load)
    maximum=model.new_int_var(0,7,f"maxload_{kind}_{identifier}");minimum=model.new_int_var(0,7,f"minload_{kind}_{identifier}");model.add_max_equality(maximum,loads);model.add_min_equality(minimum,loads)
    add_penalty("section_load_balance_penalty" if kind=="section" else "faculty_load_balance_penalty",maximum-minimum,"section_daily_load_imbalance" if kind=="section" else "faculty_daily_load_imbalance")
    if kind=="faculty":
     first=sum(occupancy[(kind,identifier,day["id"],1)] for day in days);last=sum(occupancy[(kind,identifier,day["id"],7)] for day in days)
     first_excess=model.new_int_var(0,len(days),f"first_excess_{identifier}");last_excess=model.new_int_var(0,len(days),f"last_excess_{identifier}");model.add(first_excess>=first-1);model.add(last_excess>=last-1)
     add_penalty("first_last_fairness_penalty",first_excess,"first_period_fairness");add_penalty("first_last_fairness_penalty",last_excess,"last_period_fairness")

  # Theory concentration and laboratory day spread.
  unit_count_by_offering=Counter(unit["offering"]["id"] for unit in units)
  for offering_id,offering in offerings.items():
   fixed_by_day={day["id"]:len(fixed_course_day[(offering_id,day["id"])]) for day in days};total=unit_count_by_offering[offering_id]+sum(fixed_by_day.values())
   if not total:continue
   used=[]
   for day in days:
    values=[variable for variable,_ in course_day[(offering_id,day["id"])]];day_used=model.new_bool_var(f"course_used_{offering_id}_{day['sequence_number']}")
    if fixed_by_day[day["id"]]:model.add(day_used==1)
    elif values:model.add_max_equality(day_used,values)
    else:model.add(day_used==0)
    used.append(day_used)
    excess=model.new_int_var(0,total,f"course_excess_{offering_id}_{day['sequence_number']}");model.add(excess>=sum(values)+fixed_by_day[day["id"]]-1)
    if offering["course_type"]=="THEORY":add_penalty("theory_distribution_penalty",excess,"same_course_same_day_excess")
   concentration=total-sum(used)
   if offering["course_type"]=="THEORY":add_penalty("theory_distribution_penalty",concentration,"theory_distribution_across_days")
   if offering["course_type"]=="LABORATORY":add_penalty("laboratory_placement_penalty",concentration,"laboratory_day_spread")

  # Candidate-local preference and laboratory-placement costs.
  for record in assignments:
   variable=record["var"];day_name=day_names[record["day_id"]];faculties=record["faculty_ids"]
   avoid_count=sum((faculty,day_name,period) in avoided for faculty in faculties for period in record["occupied"])
   if avoid_count:add_penalty("preference_penalty",variable,"faculty_avoid_slot_violation",avoid_count)
   preferred_misses=sum(faculty in faculty_with_preferences and not any((faculty,day_name,period) in preferred for period in record["occupied"]) for faculty in faculties)
   if preferred_misses:add_penalty("preference_penalty",variable,"faculty_preferred_slot_violation",preferred_misses)
   preferred_room=record["unit"].get("classroom_id") if record["unit"].get("combined_group_id") else primary.get(record["unit"]["section_id"])
   if record.get("classroom_id") and preferred_room and record["classroom_id"]!=preferred_room:add_penalty("room_change_penalty",variable,"room_change")
   preferred_lab=record["unit"].get("laboratory_id") if record["unit"].get("combined_group_id") else record["unit"]["offering"].get("preferred_laboratory_id")
   if record.get("laboratory_id") and preferred_lab and record["laboratory_id"]!=preferred_lab:add_penalty("room_change_penalty",variable,"room_change")
   for faculty in faculties:
    policy=policy_by_faculty.get(faculty,{})
    if policy.get("avoid_first_period") and 1 in record["occupied"]:add_penalty("preference_penalty",variable,"first_period_fairness")
    if policy.get("avoid_last_period") and 7 in record["occupied"]:add_penalty("preference_penalty",variable,"last_period_fairness")
   if record["unit"]["entry_type"]=="LABORATORY":
    if record["start"]>1:add_penalty("laboratory_placement_penalty",variable,"laboratory_first_period_preference",record["start"]-1)
    if 7 in record["occupied"]:add_penalty("laboratory_placement_penalty",variable,"laboratory_last_period_penalty")

  objective=sum(expression*coefficient for terms in penalty_terms.values() for expression,coefficient in terms)
  model.minimize(objective)

  solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=float(time_limit);solver.parameters.random_seed=seed;solver.parameters.num_search_workers=1
  status=solver.solve(model);status_name="OPTIMAL" if status==cp_model.OPTIMAL else "FEASIBLE" if status==cp_model.FEASIBLE else "INFEASIBLE" if status==cp_model.INFEASIBLE else "FAILED"
  soft_constraint_count=sum(len(terms) for terms in penalty_terms.values())
  statistics={"unit_count":len(units),"slot_count":len(days)*7,"candidate_count":len(assignments),"locked_entry_count":len(snapshot["locked_entries"]),"fixed_entry_count":len(fixed),"constraint_count":len(model.Proto().constraints),"hard_constraint_count":hard_constraint_count,"soft_constraint_count":soft_constraint_count,"optimization_profile":optimization_profile,"configured_time_limit_seconds":time_limit,"deterministic_seed":seed,"weights":{name:item.weight for name,item in optimization_config.items()},"conflicts":solver.num_conflicts,"branches":solver.num_branches,"wall_time_seconds":solver.wall_time,"input_errors":input_errors}
  if status_name=="INFEASIBLE":return {"status":"INFEASIBLE","entries":[],"message":"No feasible timetable satisfies the hard constraints","statistics":statistics}
  if status_name=="FAILED":return {"status":"FAILED","entries":[],"message":"CP-SAT did not find a feasible result within the configured execution limits","statistics":statistics}
  entries=[];selected_records=[]
  for record in assignments:
   if not solver.boolean_value(record["var"]):continue
   unit=record["unit"]
   if unit.get("rotation_block_id"):
    for child_index,child in enumerate(unit["children"]):entries.append({"course_offering_id":UUID(child["offering"]["id"]),"section_id":UUID(unit["section_id"]),"faculty_id":UUID(child["faculty_id"]) if child["faculty_id"] else None,"laboratory_faculty_allocation_id":UUID(child["lab_allocation_id"]) if child["lab_allocation_id"] else None,"classroom_id":None,"laboratory_id":UUID(record["laboratory_ids"][child_index]),"student_batch_id":UUID(child["batch_id"]),"laboratory_rotation_block_id":UUID(unit["rotation_block_id"]),"laboratory_rotation_assignment_id":UUID(child["assignment_id"]),"working_day_id":UUID(record["day_id"]),"period_number":record["start"],"session_length":unit["length"],"entry_type":child["entry_type"]})
   elif unit.get("combined_group_id"):
    event_key=f"{unit['combined_group_id']}:{unit['session_number']}"
    for child in unit["children"]:entries.append({"course_offering_id":UUID(child["offering"]["id"]),"section_id":UUID(child["section_id"]),"faculty_id":UUID(unit["faculty_id"]),"laboratory_faculty_allocation_id":None,"classroom_id":UUID(record["classroom_id"]) if record["classroom_id"] else None,"laboratory_id":UUID(record["laboratory_id"]) if record["laboratory_id"] else None,"student_batch_id":None,"laboratory_rotation_block_id":None,"laboratory_rotation_assignment_id":None,"working_day_id":UUID(record["day_id"]),"period_number":record["start"],"session_length":unit["length"],"entry_type":unit["entry_type"],"_combined_group_id":UUID(unit["combined_group_id"]),"_combined_event_key":event_key})
   else:entries.append({"course_offering_id":UUID(unit["offering"]["id"]),"section_id":UUID(unit["section_id"]),"faculty_id":UUID(unit["faculty_id"]) if unit["faculty_id"] else None,"laboratory_faculty_allocation_id":UUID(unit["lab_allocation_id"]) if unit["lab_allocation_id"] else None,"classroom_id":UUID(record["classroom_id"]) if record["classroom_id"] else None,"laboratory_id":UUID(record["laboratory_id"]) if record["laboratory_id"] else None,"student_batch_id":UUID(unit["batch_id"]) if unit["batch_id"] else None,"laboratory_rotation_block_id":None,"laboratory_rotation_assignment_id":None,"combined_teaching_event_id":None,"working_day_id":UUID(record["day_id"]),"period_number":record["start"],"session_length":unit["length"],"entry_type":unit["entry_type"]})
   selected_records.append(record)

  objective_breakdown={family:float(sum(solver.value(expression)*coefficient for expression,coefficient in penalty_terms.get(family,[]))) for family in ("theory_distribution_penalty","adjacency_penalty","section_gap_penalty","faculty_gap_penalty","preference_penalty","first_last_fairness_penalty","faculty_load_balance_penalty","section_load_balance_penalty","room_change_penalty","laboratory_placement_penalty")}
  total_penalty=float(sum(objective_breakdown.values()));quality_score=round(max(0.0,10000.0/(100.0+total_penalty)),2);objective_value=float(solver.objective_value);bound=float(solver.best_objective_bound);solver_gap=max(0.0,(objective_value-bound)/max(1.0,abs(objective_value)))
  faculty_loads=defaultdict(lambda:defaultdict(int));section_loads=defaultdict(lambda:defaultdict(int));faculty_slots=defaultdict(set);section_slots=defaultdict(set);course_distribution=defaultdict(lambda:defaultdict(int));laboratory_distribution=defaultdict(lambda:defaultdict(int));section_rooms=defaultdict(list)
  def collect(course_id,section_ids,faculty_ids,day_id,start,length,entry_type,classroom_id):
   course_distribution[str(course_id)][str(day_id)]+=1
   if entry_type=="LABORATORY":laboratory_distribution[str(course_id)][str(day_id)]+=1
   for period in range(start,start+length):
    for section_id in section_ids:section_loads[str(section_id)][str(day_id)]+=1;section_slots[(str(section_id),str(day_id))].add(period)
    for faculty in faculty_ids:faculty_loads[str(faculty)][str(day_id)]+=1;faculty_slots[(str(faculty),str(day_id))].add(period)
   if classroom_id:
    for section_id in section_ids:section_rooms[(str(section_id),str(day_id))].append((start,str(classroom_id)))
  for record in selected_records:
   unit=record["unit"]
   if unit.get("combined_group_id"):
    for course_id in {child["offering"]["id"] for child in unit["children"] if child["offering"]["id"]!=unit["offering"]["id"]}:course_distribution[str(course_id)][str(record["day_id"])]+=1
   collect(unit["offering"]["id"],unit.get("section_ids",[unit["section_id"]]),record["faculty_ids"],record["day_id"],record["start"],unit["length"],unit["entry_type"],record["classroom_id"])
  seen_fixed_quality=set()
  for item in fixed.values():
   faculty_id=item.get("faculty_id") or allocation_faculty.get(item.get("laboratory_faculty_allocation_id"));rotation_assignment=rotation_assignment_by_id.get(item.get("laboratory_rotation_assignment_id"),{});fixed_faculties={value for value in [faculty_id,rotation_assignment.get("main_faculty_id"),*(rotation_assignment.get("supporting_faculty_ids") or [])] if value};shared=item.get("combined_teaching_event_id");faculty_values=set() if shared in seen_fixed_quality else fixed_faculties;collect(item["course_offering_id"],[item["section_id"]],faculty_values,item["working_day_id"],item["period_number"],item["session_length"],item["entry_type"],item.get("classroom_id"));seen_fixed_quality.add(shared) if shared else None
  def gaps(slots):
   return 0 if not slots else sum(period not in slots for period in range(min(slots),max(slots)+1))
  faculty_gap_counts=defaultdict(int);section_gap_counts=defaultdict(int);first_last=defaultdict(lambda:{"first":0,"last":0})
  for (faculty,day_id),slots in faculty_slots.items():faculty_gap_counts[faculty]+=gaps(slots);first_last[faculty]["first"]+=int(1 in slots);first_last[faculty]["last"]+=int(7 in slots)
  for (section,day_id),slots in section_slots.items():section_gap_counts[section]+=gaps(slots)
  room_changes=defaultdict(int)
  for (section,day_id),values in section_rooms.items():
   rooms=[room for _,room in sorted(values)];room_changes[section]+=sum(left!=right for left,right in zip(rooms,rooms[1:]))
  quality_metrics={"optimization_profile":optimization_profile,"total_penalty":total_penalty,"quality_score":quality_score,"objective_breakdown":objective_breakdown,"faculty_daily_loads":{key:dict(value) for key,value in faculty_loads.items()},"faculty_first_last_counts":dict(first_last),"faculty_idle_gap_counts":dict(faculty_gap_counts),"section_daily_loads":{key:dict(value) for key,value in section_loads.items()},"section_idle_gap_counts":dict(section_gap_counts),"course_day_distribution":{key:dict(value) for key,value in course_distribution.items()},"laboratory_day_distribution":{key:dict(value) for key,value in laboratory_distribution.items()},"room_change_counts":dict(room_changes)}
  selected_supporting=[{"course_offering_id":record["unit"]["offering"]["id"],"session_number":record["unit"].get("session_number"),"student_batch_id":record["unit"].get("batch_id"),"faculty_ids":[faculty for faculty in record["faculty_ids"] if faculty!=record["unit"]["faculty_id"]]} for record in selected_records if record["unit"]["entry_type"]=="LABORATORY" and len(record["faculty_ids"])>1]
  statistics.update({"objective_breakdown":objective_breakdown,"total_objective_value":objective_value,"total_penalty":total_penalty,"solution_quality_score":quality_score,"quality_score_formula":"max(0, 10000 / (100 + total_penalty))","solver_gap":solver_gap,"selected_supporting_faculty":selected_supporting,"quality_metrics":quality_metrics})
  return {"status":status_name,"entries":entries,"objective_value":objective_value,"best_bound":bound,"message":"Optimized feasible timetable generated using Phase 2 weighted soft constraints","statistics":statistics}

solver_service=TimetableSolverService()
