from collections import Counter,defaultdict
from datetime import datetime,timezone
from itertools import combinations
from math import ceil
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func,select
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import User
from app.modules.course_offerings.models import CourseOffering
from app.modules.combined_teaching.models import CombinedTeachingEvent, CombinedTeachingGroup
from app.modules.courses.models import Course
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.resource_availability.service import availability_service
from app.modules.laboratory_batches.models import LaboratoryRotationAssignment,StudentBatch
from app.modules.programs.models import Program
from app.modules.schedule_configuration.models import PeriodTiming,WorkingDay
from app.modules.sections.models import Section
from app.modules.timetables.entry_schemas import TimetableEntryCreate
from app.modules.timetables.entry_service import entry_service
from app.modules.timetables.models import Timetable,TimetableEntry,TimetableEntryAudit,TimetableStatusHistory,TimetableVersion

IMMUTABLE={"APPROVED","PUBLISHED","ARCHIVED"}

def json_value(value):
 if isinstance(value,UUID):return str(value)
 if isinstance(value,datetime):return value.isoformat()
 return value

class TimetableReviewService:
 def _context(self,db,version_id):
  version=db.get(TimetableVersion,version_id)
  if not version:raise HTTPException(404,"Timetable version not found")
  timetable=db.get(Timetable,version.timetable_id)
  if not timetable:raise HTTPException(404,"Timetable not found")
  return version,timetable
 def _roles(self,user):return {role.name for role in user.roles}
 def _department_for_entry(self,db,entry):
  section=db.get(Section,entry.section_id);program=db.get(Program,section.program_id) if section else None;return program.department_id if program else None
 def _enforce_entry_scope(self,db,user,entry):
  roles=self._roles(user)
  if roles&{"Administrator","Timetable Coordinator"}:return
  if "HOD" in roles:
   faculty=db.scalar(select(Faculty).where(Faculty.user_id==user.id,Faculty.is_active.is_(True)))
   if faculty and faculty.department_id==self._department_for_entry(db,entry):return
  raise HTTPException(403,"Entry is outside the user's permitted department scope")
 def _entry_values(self,entry):
  fields=("course_offering_id","section_id","faculty_id","laboratory_faculty_allocation_id","classroom_id","laboratory_id","student_batch_id","laboratory_rotation_block_id","laboratory_rotation_assignment_id","combined_teaching_event_id","working_day_id","period_number","session_length","entry_type","is_manual","is_locked")
  return {field:json_value(getattr(entry,field)) for field in fields}
 def _audit(self,db,entry,action,user_id,old=None,new=None,reason=None):
  audit=TimetableEntryAudit(timetable_entry_id=entry.id,timetable_version_id=entry.timetable_version_id,action_type=action,old_values_json=old,new_values_json=new,reason=reason,performed_by=user_id,created_at=datetime.now(timezone.utc));db.add(audit);return audit
 def _mark_stale(self,db,version_id):
  version=db.get(TimetableVersion,version_id);version.solver_status="STALE";version.updated_at=datetime.now(timezone.utc)
 def _block_entries(self,db,entry):
  if entry.combined_teaching_event_id:return list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==entry.timetable_version_id,TimetableEntry.combined_teaching_event_id==entry.combined_teaching_event_id).order_by(TimetableEntry.section_id,TimetableEntry.id)))
  if not entry.laboratory_rotation_block_id:return [entry]
  return list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==entry.timetable_version_id,TimetableEntry.laboratory_rotation_block_id==entry.laboratory_rotation_block_id).order_by(TimetableEntry.student_batch_id,TimetableEntry.id)))

 def grid(self,db,version_id,view_type,resource_id,user):
  version,timetable=self._context(db,version_id);roles=self._roles(user)
  if "Student" in roles and (view_type!="section" or timetable.status!="PUBLISHED"):raise HTTPException(403,"Students may view published section timetables only")
  if "Faculty" in roles and not roles&{"Administrator","Timetable Coordinator","HOD","Dean","Principal"}:
   own=db.scalar(select(Faculty.id).where(Faculty.user_id==user.id));
   if view_type!="faculty" or own!=resource_id:raise HTTPException(403,"Faculty may view only their own timetable")
  all_entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id).order_by(TimetableEntry.working_day_id,TimetableEntry.period_number,TimetableEntry.id)));entries=list(all_entries)
  if view_type=="section":entries=[x for x in entries if x.section_id==resource_id]
  elif view_type=="classroom":entries=[x for x in entries if x.classroom_id==resource_id]
  elif view_type=="laboratory":entries=[x for x in entries if x.laboratory_id==resource_id]
  elif view_type=="batch":entries=[x for x in entries if x.student_batch_id==resource_id]
  elif view_type=="faculty":
   allocation_ids=set(db.scalars(select(LaboratoryFacultyAllocation.id).where(LaboratoryFacultyAllocation.faculty_id==resource_id)));entries=[x for x in entries if x.faculty_id==resource_id or x.laboratory_faculty_allocation_id in allocation_ids]
  else:raise HTTPException(422,"Unknown timetable view")
  if view_type in {"faculty","classroom","laboratory"}:
   seen=set();entries=[entry for entry in entries if not entry.combined_teaching_event_id or entry.combined_teaching_event_id not in seen and not seen.add(entry.combined_teaching_event_id)]
  term=db.get(AcademicTerm,timetable.academic_term_id);schedule_type="FIRST_YEAR" if term and term.year_number==1 else "HIGHER_YEAR"
  days=list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True)).order_by(WorkingDay.sequence_number,WorkingDay.id)));timings={x.period_number:x for x in db.scalars(select(PeriodTiming).where(PeriodTiming.schedule_type==schedule_type,PeriodTiming.is_active.is_(True),PeriodTiming.is_instructional.is_(True)))}
  offering_ids={x.course_offering_id for x in entries};offerings={x.id:x for x in db.scalars(select(CourseOffering).where(CourseOffering.id.in_(offering_ids)))} if offering_ids else {};courses={x.id:x for x in db.scalars(select(Course).where(Course.id.in_({x.course_id for x in offerings.values()})))} if offerings else {};all_section_ids={x.section_id for x in all_entries if x.combined_teaching_event_id in {e.combined_teaching_event_id for e in entries if e.combined_teaching_event_id}}|{x.section_id for x in entries};sections={x.id:x for x in db.scalars(select(Section).where(Section.id.in_(all_section_ids)))} if all_section_ids else {};faculty={x.id:x for x in db.scalars(select(Faculty).where(Faculty.id.in_({x.faculty_id for x in entries if x.faculty_id})))} if entries else {};classrooms={x.id:x for x in db.scalars(select(Classroom).where(Classroom.id.in_({x.classroom_id for x in entries if x.classroom_id})))} if entries else {};labs={x.id:x for x in db.scalars(select(Laboratory).where(Laboratory.id.in_({x.laboratory_id for x in entries if x.laboratory_id})))} if entries else {};batches={x.id:x for x in db.scalars(select(StudentBatch).where(StudentBatch.id.in_({x.student_batch_id for x in entries if x.student_batch_id})))} if entries else {}
  event_ids={x.combined_teaching_event_id for x in entries if x.combined_teaching_event_id};events={x.id:x for x in db.scalars(select(CombinedTeachingEvent).where(CombinedTeachingEvent.id.in_(event_ids)))} if event_ids else {};groups={x.id:x for x in db.scalars(select(CombinedTeachingGroup).where(CombinedTeachingGroup.id.in_({x.combined_teaching_group_id for x in events.values()})))} if events else {};combined_sections=defaultdict(list)
  for child in all_entries:
   if child.combined_teaching_event_id in event_ids and child.section_id in sections:combined_sections[child.combined_teaching_event_id].append(sections[child.section_id].section_code)
  allocation_map={x.id:x.faculty_id for x in db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id.in_({x.laboratory_faculty_allocation_id for x in entries if x.laboratory_faculty_allocation_id})))} if entries else {}
  missing_faculty={value for value in allocation_map.values() if value not in faculty};faculty.update({x.id:x for x in db.scalars(select(Faculty).where(Faculty.id.in_(missing_faculty)))}) if missing_faculty else None
  by_day=defaultdict(list);day_by_id={x.id:x for x in days}
  for entry in entries:
   offering=offerings.get(entry.course_offering_id);course=courses.get(offering.course_id) if offering else None;member=faculty.get(entry.faculty_id or allocation_map.get(entry.laboratory_faculty_allocation_id));start=timings.get(entry.period_number);end=timings.get(entry.period_number+entry.session_length-1)
   if not start or not end:continue
   event=events.get(entry.combined_teaching_event_id);group=groups.get(event.combined_teaching_group_id) if event else None
   by_day[entry.working_day_id].append({"entry_id":entry.id,"laboratory_rotation_block_id":entry.laboratory_rotation_block_id,"combined_teaching_event_id":entry.combined_teaching_event_id,"combined_teaching_group_code":group.group_code if group else None,"combined_section_codes":sorted(combined_sections.get(entry.combined_teaching_event_id,[])),"working_day_id":entry.working_day_id,"day_name":day_by_id.get(entry.working_day_id).day_name if day_by_id.get(entry.working_day_id) else "Unknown","period_number":entry.period_number,"period_numbers":list(range(entry.period_number,entry.period_number+entry.session_length)),"schedule_type":schedule_type,"start_time":start.start_time,"end_time":end.end_time,"course_code":course.course_code if course else "","course_name":course.course_name if course else "","course_type":course.course_type if course else entry.entry_type,"section_code":sections.get(entry.section_id).section_code if sections.get(entry.section_id) else "","faculty_code":member.faculty_code if member else None,"faculty_name":member.full_name if member else None,"classroom_room_number":classrooms.get(entry.classroom_id).room_number if classrooms.get(entry.classroom_id) else None,"laboratory_code":labs.get(entry.laboratory_id).laboratory_code if labs.get(entry.laboratory_id) else None,"laboratory_name":labs.get(entry.laboratory_id).laboratory_name if labs.get(entry.laboratory_id) else None,"batch_name":batches.get(entry.student_batch_id).batch_name if batches.get(entry.student_batch_id) else None,"session_length":entry.session_length,"entry_status":"LOCKED" if entry.is_locked else "MANUAL" if entry.is_manual else "GENERATED","is_manual":entry.is_manual,"is_locked":entry.is_locked})
  return {"version_id":version.id,"view_type":view_type,"resource_id":resource_id,"schedule_type":schedule_type,"days":[{"working_day_id":day.id,"day_name":day.day_name,"sequence_number":day.sequence_number,"entries":sorted(by_day[day.id],key=lambda x:(x["period_number"],str(x["entry_id"]))) } for day in days]}

 def move(self,db,entry,payload,user):
  siblings=self._block_entries(db,entry)
  if any(sibling.is_locked for sibling in siblings):raise HTTPException(409,"Locked timetable entry must be explicitly unlocked before moving")
  self._enforce_entry_scope(db,user,entry);version,timetable=self._context(db,entry.timetable_version_id)
  if not version.is_active or version.is_locked or timetable.status in IMMUTABLE:raise HTTPException(409,"Immutable timetable version cannot be modified")
  if entry.laboratory_rotation_block_id and (payload.classroom_id is not None or payload.laboratory_id is not None):raise HTTPException(422,"Rotation block movement preserves each child facility; edit the matrix to change facilities")
  updates=[]
  for sibling in siblings:
   old=self._entry_values(sibling);values={field:getattr(sibling,field) for field in TimetableEntryCreate.model_fields};values.update({"working_day_id":payload.working_day_id,"period_number":payload.period_number})
   if payload.classroom_id is not None:values["classroom_id"]=payload.classroom_id
   if payload.laboratory_id is not None:values["laboratory_id"]=payload.laboratory_id
   values["is_manual"]=True;values["is_locked"]=payload.lock_after_move;validated=TimetableEntryCreate(**values);entry_service._validate(db,sibling.timetable_version_id,validated,sibling.id);updates.append((sibling,old,values))
  now=datetime.now(timezone.utc)
  for sibling,old,values in updates:
   for key,value in values.items():setattr(sibling,key,value)
   sibling.updated_at=now;self._audit(db,sibling,"MOVED",user.id,old,self._entry_values(sibling),"Atomic synchronized event move" if len(siblings)>1 else None)
  if entry.combined_teaching_event_id:
   event=db.get(CombinedTeachingEvent,entry.combined_teaching_event_id);event.working_day_id=payload.working_day_id;event.period_number=payload.period_number;event.classroom_id=payload.classroom_id if payload.classroom_id is not None else event.classroom_id;event.laboratory_id=payload.laboratory_id if payload.laboratory_id is not None else event.laboratory_id;event.is_manual=True;event.is_locked=payload.lock_after_move;event.updated_at=now
  self._mark_stale(db,entry.timetable_version_id);db.commit();db.refresh(entry);return entry
 def lock(self,db,entry,user,reason=None):
  self._enforce_entry_scope(db,user,entry);version,timetable=self._context(db,entry.timetable_version_id)
  if timetable.status in IMMUTABLE:raise HTTPException(409,"Immutable timetable cannot be changed")
  siblings=self._block_entries(db,entry)
  if all(sibling.is_locked for sibling in siblings):raise HTTPException(409,"Timetable entry is already locked")
  now=datetime.now(timezone.utc)
  for sibling in siblings:
   if sibling.is_locked:continue
   old=self._entry_values(sibling);sibling.is_locked=True;sibling.updated_at=now;self._audit(db,sibling,"LOCKED",user.id,old,self._entry_values(sibling),reason)
  if entry.combined_teaching_event_id:
   event=db.get(CombinedTeachingEvent,entry.combined_teaching_event_id);event.is_locked=True;event.updated_at=now
  self._mark_stale(db,version.id);db.commit();db.refresh(entry);return entry
 def unlock(self,db,entry,user,reason):
  self._enforce_entry_scope(db,user,entry);version,timetable=self._context(db,entry.timetable_version_id)
  if timetable.status in {"APPROVED","PUBLISHED","ARCHIVED"} or version.is_locked:raise HTTPException(409,"Approved or published timetable versions cannot be unlocked")
  siblings=self._block_entries(db,entry)
  if not any(sibling.is_locked for sibling in siblings):raise HTTPException(409,"Timetable entry is not locked")
  now=datetime.now(timezone.utc)
  for sibling in siblings:
   if not sibling.is_locked:continue
   old=self._entry_values(sibling);sibling.is_locked=False;sibling.updated_at=now;self._audit(db,sibling,"UNLOCKED",user.id,old,self._entry_values(sibling),reason)
  if entry.combined_teaching_event_id:
   event=db.get(CombinedTeachingEvent,entry.combined_teaching_event_id);event.is_locked=False;event.updated_at=now
  self._mark_stale(db,version.id);db.commit();db.refresh(entry);return entry
 def audits(self,db,entry_id):return list(db.scalars(select(TimetableEntryAudit).where(TimetableEntryAudit.timetable_entry_id==entry_id).order_by(TimetableEntryAudit.created_at,TimetableEntryAudit.id)))

 def copy_version(self,db,version_id,payload,user):
  source,timetable=self._context(db,version_id)
  if timetable.status in {"PUBLISHED","ARCHIVED"}:raise HTTPException(409,"Published or archived timetables cannot be copied into an active review version")
  number=int(db.scalar(select(func.max(TimetableVersion.version_number)).where(TimetableVersion.timetable_id==timetable.id)) or 0)+1;now=datetime.now(timezone.utc)
  for version in db.scalars(select(TimetableVersion).where(TimetableVersion.timetable_id==timetable.id,TimetableVersion.is_active.is_(True))):version.is_active=False;version.updated_at=now
  copied=TimetableVersion(timetable_id=timetable.id,version_number=number,version_name=payload.version_name,source_type=payload.source_type,validation_run_id=source.validation_run_id,solver_status="NOT_STARTED",is_active=True,is_locked=False,created_by=user.id,created_at=now,updated_at=now);db.add(copied);db.flush()
  event_map={}
  for event in db.scalars(select(CombinedTeachingEvent).where(CombinedTeachingEvent.timetable_version_id==source.id).order_by(CombinedTeachingEvent.id)):
   created_event=CombinedTeachingEvent(timetable_version_id=copied.id,combined_teaching_group_id=event.combined_teaching_group_id,working_day_id=event.working_day_id,period_number=event.period_number,session_length=event.session_length,faculty_id=event.faculty_id,classroom_id=event.classroom_id,laboratory_id=event.laboratory_id,is_manual=event.is_manual,is_locked=event.is_locked,created_at=now,updated_at=now);db.add(created_event);db.flush();event_map[event.id]=created_event.id
  for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==source.id).order_by(TimetableEntry.id)):
   values={field:getattr(entry,field) for field in TimetableEntryCreate.model_fields};values["combined_teaching_event_id"]=event_map.get(entry.combined_teaching_event_id);created=TimetableEntry(timetable_version_id=copied.id,**values,created_at=now,updated_at=now);db.add(created);db.flush();self._audit(db,created,"CREATED",user.id,None,self._entry_values(created),f"Copied from version {source.id}")
  timetable.active_version_id=copied.id;timetable.updated_at=now;db.commit();db.refresh(copied);return copied
 def compare(self,db,version_id,other_id):
  self._context(db,version_id);self._context(db,other_id)
  def semantic(version):
   rows=list(db.scalars(select(TimetableEntry).join(WorkingDay).where(TimetableEntry.timetable_version_id==version).order_by(TimetableEntry.course_offering_id,TimetableEntry.section_id,TimetableEntry.student_batch_id,WorkingDay.sequence_number,TimetableEntry.period_number,TimetableEntry.id)));counts=defaultdict(int);result={}
   for row in rows:
    base=(str(row.course_offering_id),str(row.section_id),str(row.student_batch_id or ""));index=counts[base];counts[base]+=1;result[base+(index,)]=row
   return result
  left,right=semantic(version_id),semantic(other_id);added=[];removed=[];moved=[];faculty=[];facilities=[];locks=[]
  def brief(row):
   value={"entry_id":str(row.id),"course_offering_id":str(row.course_offering_id),"section_id":str(row.section_id),"student_batch_id":str(row.student_batch_id) if row.student_batch_id else None,"working_day_id":str(row.working_day_id),"period_number":row.period_number,"faculty_id":str(row.faculty_id) if row.faculty_id else None,"classroom_id":str(row.classroom_id) if row.classroom_id else None,"laboratory_id":str(row.laboratory_id) if row.laboratory_id else None,"is_locked":row.is_locked}
   if row.combined_teaching_event_id:
    event=db.get(CombinedTeachingEvent,row.combined_teaching_event_id);group=db.get(CombinedTeachingGroup,event.combined_teaching_group_id) if event else None
    section_ids=set(db.scalars(select(TimetableEntry.section_id).where(TimetableEntry.timetable_version_id==row.timetable_version_id,TimetableEntry.combined_teaching_event_id==row.combined_teaching_event_id)))
    codes=sorted(db.scalars(select(Section.section_code).where(Section.id.in_(section_ids)))) if section_ids else []
    value.update({"common_class":group.group_code if group else "Combined class","combined_sections":" + ".join(codes)})
   return value
  for key in sorted(set(left)|set(right)):
   a,b=left.get(key),right.get(key)
   if not a:added.append(brief(b));continue
   if not b:removed.append(brief(a));continue
   pair={"from":brief(a),"to":brief(b)}
   if (a.working_day_id,a.period_number)!=(b.working_day_id,b.period_number):moved.append(pair)
   if (a.faculty_id,a.laboratory_faculty_allocation_id)!=(b.faculty_id,b.laboratory_faculty_allocation_id):faculty.append(pair)
   if (a.classroom_id,a.laboratory_id)!=(b.classroom_id,b.laboratory_id):facilities.append(pair)
   if a.is_locked!=b.is_locked:locks.append(pair)
  return {"version_id":version_id,"other_version_id":other_id,"added_entries":added,"removed_entries":removed,"moved_entries":moved,"faculty_changes":faculty,"facility_changes":facilities,"lock_state_changes":locks,"summary":{"added":len(added),"removed":len(removed),"moved":len(moved),"faculty_changes":len(faculty),"facility_changes":len(facilities),"lock_state_changes":len(locks)}}

 def transition(self,db,timetable_id,target,user,reason=None):
  timetable=db.get(Timetable,timetable_id)
  if not timetable:raise HTTPException(404,"Timetable not found")
  allowed={"UNDER_REVIEW":{"GENERATED"},"APPROVED":{"UNDER_REVIEW"},"PUBLISHED":{"APPROVED"},"ARCHIVED":{"PUBLISHED"},"DRAFT":{"GENERATED","UNDER_REVIEW","APPROVED"}}
  if timetable.status not in allowed[target]:raise HTTPException(409,f"Invalid timetable status transition: {timetable.status} -> {target}")
  if target=="DRAFT" and not reason:raise HTTPException(422,"A reason is required when returning a timetable to draft")
  old=timetable.status;now=datetime.now(timezone.utc);timetable.status=target;timetable.updated_at=now;version=db.get(TimetableVersion,timetable.active_version_id) if timetable.active_version_id else None
  if version:
   if target in {"APPROVED","PUBLISHED","ARCHIVED"}:version.is_locked=True
   elif target=="DRAFT":version.is_locked=False
   version.updated_at=now
  history=TimetableStatusHistory(timetable_id=timetable.id,from_status=old,to_status=target,reason=reason,performed_by=user.id,created_at=now);db.add(history);db.commit();db.refresh(timetable);return timetable
 def status_history(self,db,timetable_id):
  if not db.get(Timetable,timetable_id):raise HTTPException(404,"Timetable not found")
  return list(db.scalars(select(TimetableStatusHistory).where(TimetableStatusHistory.timetable_id==timetable_id).order_by(TimetableStatusHistory.created_at,TimetableStatusHistory.id)))

 def free_resources(self,db,version_id,kind,day_id,period):
  _,timetable=self._context(db,version_id);day=db.get(WorkingDay,day_id)
  if not day or not day.is_active or not day.is_working_day:raise HTTPException(422,"Working day must be active")
  occupied=entry_service._overlapping if hasattr(entry_service,"_overlapping") else None;entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id,TimetableEntry.working_day_id==day_id,TimetableEntry.period_number<=period,(TimetableEntry.period_number+TimetableEntry.session_length-1)>=period)))
  if kind=="faculty":
   used={x.faculty_id for x in entries if x.faculty_id};used|={x.faculty_id for x in db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id.in_({e.laboratory_faculty_allocation_id for e in entries if e.laboratory_faculty_allocation_id})))} if entries else set();rows=db.scalars(select(Faculty).where(Faculty.is_active.is_(True),Faculty.id.not_in(used)).order_by(Faculty.faculty_code));items=[{"id":str(x.id),"faculty_code":x.faculty_code,"full_name":x.full_name} for x in rows if availability_service.is_available(db,"FACULTY",x.id,timetable.academic_term_id,day_id,period)]
  elif kind=="classroom":
   used={x.classroom_id for x in entries if x.classroom_id};items=[{"id":str(x.id),"room_number":x.room_number,"room_name":x.room_name} for x in db.scalars(select(Classroom).where(Classroom.is_active.is_(True),Classroom.id.not_in(used)).order_by(Classroom.room_number)) if availability_service.is_available(db,"CLASSROOM",x.id,timetable.academic_term_id,day_id,period)]
  else:
   used={x.laboratory_id for x in entries if x.laboratory_id};available=[x for x in db.scalars(select(Laboratory).where(Laboratory.is_active.is_(True),Laboratory.id.not_in(used)).order_by(Laboratory.laboratory_code)) if availability_service.is_available(db,"LABORATORY",x.id,timetable.academic_term_id,day_id,period)];items=[{"id":str(x.id),"laboratory_code":x.laboratory_code,"laboratory_name":x.laboratory_name} for x in available]
  return {"version_id":version_id,"working_day_id":day_id,"period_number":period,"items":items}

 def conflicts(self,db,version_id):
  version,timetable=self._context(db,version_id);entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id)));issues=[]
  def add(kind,entries,message):issues.append({"conflict_type":kind,"entry_ids":[str(x.id) for x in entries],"message":message})
  allocation_faculty={x.id:x.faculty_id for x in db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id.in_({e.laboratory_faculty_allocation_id for e in entries if e.laboratory_faculty_allocation_id})))} if entries else {}
  rotation_assignments={x.id:x for x in db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.id.in_({e.laboratory_rotation_assignment_id for e in entries if e.laboratory_rotation_assignment_id})))} if entries else {}
  def entry_faculties(entry):
   assignment=rotation_assignments.get(entry.laboratory_rotation_assignment_id);return {UUID(str(value)) for value in [entry.faculty_id,allocation_faculty.get(entry.laboratory_faculty_allocation_id),assignment.main_faculty_id if assignment else None,*((assignment.supporting_faculty_ids or []) if assignment else [])] if value}
  for entry in entries:
   if entry.period_number<1 or entry.period_number+entry.session_length-1>7:add("invalid_session_span",[entry],"Session lies outside periods 1-7")
  for left,right in combinations(entries,2):
   if left.working_day_id!=right.working_day_id or left.period_number+left.session_length-1<right.period_number or right.period_number+right.session_length-1<left.period_number:continue
   left_faculties=entry_faculties(left);right_faculties=entry_faculties(right)
   synchronized=left.laboratory_rotation_block_id is not None and left.laboratory_rotation_block_id==right.laboratory_rotation_block_id and left.student_batch_id!=right.student_batch_id
   same_combined=left.combined_teaching_event_id is not None and left.combined_teaching_event_id==right.combined_teaching_event_id
   for kind,clash in (("section",left.section_id==right.section_id and not synchronized),("faculty",not same_combined and bool(left_faculties&right_faculties)),("classroom",not same_combined and left.classroom_id is not None and left.classroom_id==right.classroom_id),("laboratory",not same_combined and left.laboratory_id is not None and left.laboratory_id==right.laboratory_id),("batch",left.student_batch_id is not None and left.student_batch_id==right.student_batch_id)):
    if clash:add(f"{kind}_clash",[left,right],f"Overlapping {kind} usage")
  days={x.id:x.day_name for x in db.scalars(select(WorkingDay))}
  seen_availability=set()
  for entry in entries:
   faculty_id=entry.faculty_id or allocation_faculty.get(entry.laboratory_faculty_allocation_id)
   for period in range(entry.period_number,entry.period_number+entry.session_length):
    event_key=entry.combined_teaching_event_id or entry.id
    key=(event_key,"FACULTY",faculty_id,entry.working_day_id,period)
    if faculty_id and key not in seen_availability and not availability_service.is_available(db,"FACULTY",faculty_id,timetable.academic_term_id,entry.working_day_id,period):add("unavailable_faculty_usage",[entry],"Faculty is scheduled in an unavailable slot")
    seen_availability.add(key)
    key=(event_key,"CLASSROOM",entry.classroom_id,entry.working_day_id,period)
    if entry.classroom_id and key not in seen_availability and not availability_service.is_available(db,"CLASSROOM",entry.classroom_id,timetable.academic_term_id,entry.working_day_id,period):add("unavailable_classroom_usage",[entry],"Classroom is scheduled outside its configured availability")
    seen_availability.add(key)
    if entry.laboratory_id:
     laboratory=db.get(Laboratory,entry.laboratory_id)
     key=(event_key,"LABORATORY",entry.laboratory_id,entry.working_day_id,period)
     if laboratory and key not in seen_availability and not availability_service.is_available(db,"LABORATORY",laboratory.id,timetable.academic_term_id,entry.working_day_id,period):add("blocked_laboratory_usage",[entry],"Laboratory is scheduled outside its configured availability")
     seen_availability.add(key)
  counts=Counter(item["conflict_type"] for item in issues);return {"version_id":version_id,"conflicts":issues,"summary":dict(counts)|{"total":len(issues)}}

review_service=TimetableReviewService()
