from datetime import datetime,timezone
from uuid import UUID
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.course_offerings.laboratories import resolve_effective_laboratories
from app.modules.combined_teaching.models import CombinedTeachingEvent, CombinedTeachingGroupMember
from app.modules.courses.models import Course
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.resource_availability.service import availability_service
from app.modules.laboratory_batches.models import LaboratoryBatchConfiguration,LaboratoryRotationAssignment,LaboratoryRotationBlock,StudentBatch
from app.modules.schedule_configuration.models import PeriodTiming,WorkingDay
from app.modules.timetables.entry_repository import entry_repository
from app.modules.timetables.entry_schemas import TimetableEntryCreate
from app.modules.timetables.models import Timetable,TimetableEntry,TimetableEntryAudit,TimetableVersion
from app.modules.timetables.capacity import entry_capacity_demand,logical_capacity_key

IMMUTABLE_TIMETABLE_STATUSES={"APPROVED","PUBLISHED","ARCHIVED"}

class TimetableEntryService:
 def _values(self,entry):
  return {field:(str(value) if hasattr(value,"hex") else value) for field in TimetableEntryCreate.model_fields for value in [getattr(entry,field)]}
 def _audit(self,db,entry,action,user_id,old=None,new=None,reason=None):
  if user_id:db.add(TimetableEntryAudit(timetable_entry_id=entry.id,timetable_version_id=entry.timetable_version_id,action_type=action,old_values_json=old,new_values_json=new,reason=reason,performed_by=user_id,created_at=datetime.now(timezone.utc)))
 def _version_context(self,db,version_id):
  version=db.scalar(select(TimetableVersion).where(TimetableVersion.id==version_id))
  if not version:raise HTTPException(404,"Timetable version not found")
  timetable=db.scalar(select(Timetable).where(Timetable.id==version.timetable_id))
  if not timetable:raise HTTPException(404,"Timetable not found")
  if not version.is_active:raise HTTPException(409,"Inactive timetable version cannot be modified")
  if version.is_locked:raise HTTPException(409,"Locked timetable version cannot be modified")
  if timetable.status in IMMUTABLE_TIMETABLE_STATUSES:raise HTTPException(409,"Immutable timetable cannot be modified")
  return version,timetable

 def _validate(self,db,version_id,data,exclude_id=None):
  _,timetable=self._version_context(db,version_id)
  offering=db.scalar(select(CourseOffering).where(CourseOffering.id==data.course_offering_id))
  if not offering or not offering.is_active:raise HTTPException(422,"Course offering must be active")
  if offering.section_id!=data.section_id:raise HTTPException(422,"Entry section must match course offering section")
  if offering.academic_term_id!=timetable.academic_term_id:raise HTTPException(422,"Course offering academic term must match timetable")
  if data.combined_teaching_event_id:
   event=db.get(CombinedTeachingEvent,data.combined_teaching_event_id)
   member=db.scalar(select(CombinedTeachingGroupMember).where(CombinedTeachingGroupMember.combined_teaching_group_id==(event.combined_teaching_group_id if event else None),CombinedTeachingGroupMember.course_offering_id==offering.id,CombinedTeachingGroupMember.is_active.is_(True)))
   if not event or event.timetable_version_id!=version_id or not member:raise HTTPException(422,"Combined teaching child must belong to the configured logical event")
  course=db.scalar(select(Course).where(Course.id==offering.course_id))
  if not course or not course.is_active:raise HTTPException(422,"Course must be active")
  if course.course_type!=data.entry_type:raise HTTPException(422,"Entry type must match course type")
  if data.period_number+data.session_length-1>7:raise HTTPException(422,"Session must not exceed period 7")
  day=db.scalar(select(WorkingDay).where(WorkingDay.id==data.working_day_id))
  if not day or not day.is_active or not day.is_working_day:raise HTTPException(422,"Working day must be active")

  faculty_for_constraints=data.faculty_id
  if data.laboratory_faculty_allocation_id:
   allocation=db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id==data.laboratory_faculty_allocation_id))
   if not allocation or not allocation.is_active or allocation.course_offering_id!=offering.id:raise HTTPException(422,"Laboratory faculty allocation must be active and belong to the offering")
   if data.faculty_id and data.faculty_id!=allocation.faculty_id:raise HTTPException(422,"Faculty does not match laboratory allocation")
   faculty_for_constraints=allocation.faculty_id
  if faculty_for_constraints:
   faculty=db.scalar(select(Faculty).where(Faculty.id==faculty_for_constraints))
   if not faculty or not faculty.is_active:raise HTTPException(422,"Faculty must be active")
  if data.classroom_id:
   classroom=db.scalar(select(Classroom).where(Classroom.id==data.classroom_id))
   if not classroom or not classroom.is_active:raise HTTPException(422,"Classroom must be active")
  laboratory=None
  if data.laboratory_id:
   laboratory=db.scalar(select(Laboratory).where(Laboratory.id==data.laboratory_id))
   if not laboratory or not laboratory.is_active:raise HTTPException(422,"Laboratory must be active")
   effective_ids={item.id for item in resolve_effective_laboratories(db,course,offering)}
   if laboratory.id not in effective_ids:raise HTTPException(422,"Laboratory must be permitted by the course offering")

  if data.session_length!=course.session_duration:raise HTTPException(422,"Session length must match the course session pattern")
  if course.course_type in {"THEORY","CDC","PRACTICAL"} and not data.faculty_id:raise HTTPException(422,"The academic activity requires an assigned faculty member")
  if course.venue_requirement=="CLASSROOM_ONLY" and (not data.classroom_id or data.laboratory_id):raise HTTPException(422,"CLASSROOM_ONLY requires a classroom and cannot use a laboratory")
  if course.venue_requirement=="LABORATORY_ONLY" and (not data.laboratory_id or data.classroom_id):raise HTTPException(422,"LABORATORY_ONLY requires a laboratory and cannot use a classroom")
  if course.venue_requirement=="CLASSROOM_OR_LABORATORY" and bool(data.classroom_id)==bool(data.laboratory_id):raise HTTPException(422,"CLASSROOM_OR_LABORATORY requires exactly one classroom or laboratory")
  configuration=db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id==offering.id,LaboratoryBatchConfiguration.is_active.is_(True)))
  effective_count=configuration.number_of_groups if configuration else course.default_group_count
  if course.grouping_mode=="GROUPED" and (effective_count or 0)>1 and not data.student_batch_id:raise HTTPException(422,"A student group is required for this grouped offering")
  if course.grouping_mode=="FULL_SECTION" and data.student_batch_id:raise HTTPException(422,"FULL_SECTION entries cannot select a student group")
  if data.session_length>1:self._validate_lab_lunch(db,timetable.academic_term_id,data.period_number,data.session_length)

  if data.student_batch_id:
   batch=db.scalar(select(StudentBatch).where(StudentBatch.id==data.student_batch_id))
   if not batch or not batch.is_active or batch.section_id!=data.section_id:raise HTTPException(422,"Student batch must be active and belong to the section")

  constraint_faculty_ids={faculty_for_constraints} if faculty_for_constraints else set()
  if bool(data.laboratory_rotation_block_id)!=bool(data.laboratory_rotation_assignment_id):raise HTTPException(422,"Rotation block and assignment must be supplied together")
  if data.laboratory_rotation_assignment_id:
   rotation_assignment=db.get(LaboratoryRotationAssignment,data.laboratory_rotation_assignment_id);rotation_block=db.get(LaboratoryRotationBlock,data.laboratory_rotation_block_id)
   if not rotation_assignment or not rotation_assignment.is_active or not rotation_block or not rotation_block.is_active or rotation_assignment.rotation_block_id!=rotation_block.id:raise HTTPException(422,"Rotation assignment must belong to the active rotation block")
   if (rotation_assignment.course_offering_id,rotation_assignment.batch_id)!=(data.course_offering_id,data.student_batch_id) or rotation_assignment.laboratory_id and rotation_assignment.laboratory_id!=data.laboratory_id:raise HTTPException(422,"Timetable entry resources must match the rotation assignment")
   if rotation_assignment.main_faculty_id and faculty_for_constraints!=rotation_assignment.main_faculty_id:raise HTTPException(422,"Timetable entry faculty must match the rotation assignment")
   constraint_faculty_ids|={UUID(str(value)) for value in rotation_assignment.supporting_faculty_ids or []}

  periods=range(data.period_number,data.period_number+data.session_length)
  if data.classroom_id and any(not availability_service.is_available(db,"CLASSROOM",data.classroom_id,timetable.academic_term_id,data.working_day_id,period) for period in periods):raise HTTPException(409,"Classroom is unavailable during the requested session")
  if laboratory and any(not availability_service.is_available(db,"LABORATORY",laboratory.id,timetable.academic_term_id,data.working_day_id,period) for period in periods):raise HTTPException(409,"Laboratory is blocked or unavailable during the requested session")
  if any(not availability_service.is_available(db,"FACULTY",faculty_id,timetable.academic_term_id,data.working_day_id,period) for faculty_id in constraint_faculty_ids for period in periods):raise HTTPException(409,"Faculty is unavailable during the requested session")

  demand=entry_capacity_demand(db,data)
  if laboratory and laboratory.capacity is not None and demand>laboratory.capacity:raise HTTPException(409,f"{laboratory.laboratory_name} {laboratory.room_number} has capacity {laboratory.capacity}; the selected activity requires capacity for {demand} students.")

  conflicts=[];overlapping=entry_repository.overlapping(db,version_id,data.working_day_id,data.period_number,data.period_number+data.session_length-1,exclude_id)
  for existing in overlapping:
   same_combined=data.combined_teaching_event_id is not None and data.combined_teaching_event_id==existing.combined_teaching_event_id
   parallel_groups=(data.student_batch_id is not None and existing.student_batch_id is not None and existing.student_batch_id!=data.student_batch_id)
   if existing.section_id==data.section_id and not parallel_groups:conflicts.append("section")
   existing_faculties={existing.faculty_id} if existing.faculty_id else set()
   if existing.laboratory_faculty_allocation_id:
    allocation=db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id==existing.laboratory_faculty_allocation_id));existing_faculties|={allocation.faculty_id} if allocation else set()
   if existing.laboratory_rotation_assignment_id:
    assignment=db.get(LaboratoryRotationAssignment,existing.laboratory_rotation_assignment_id);existing_faculties|={UUID(str(value)) for value in ([assignment.main_faculty_id,*assignment.supporting_faculty_ids] if assignment else []) if value}
   if not same_combined and constraint_faculty_ids&existing_faculties:conflicts.append("faculty")
   if not same_combined and data.classroom_id and existing.classroom_id==data.classroom_id:conflicts.append("classroom")
   if not same_combined and data.laboratory_id and existing.laboratory_id==data.laboratory_id and laboratory.concurrent_usage_mode!="CAPACITY_SHARED":conflicts.append("laboratory")
   if data.student_batch_id and existing.student_batch_id==data.student_batch_id:conflicts.append("student_batch")
  if conflicts:raise HTTPException(409,"Overlapping timetable entry conflicts: "+", ".join(sorted(set(conflicts))))
  if laboratory and laboratory.concurrent_usage_mode=="CAPACITY_SHARED":
   capacity=int(laboratory.capacity or 0)
   for period in periods:
    logical={}
    for existing in overlapping:
     if existing.laboratory_id!=laboratory.id or not (existing.period_number<=period<=existing.period_number+existing.session_length-1):continue
     if data.combined_teaching_event_id and existing.combined_teaching_event_id==data.combined_teaching_event_id:continue
     logical.setdefault(logical_capacity_key(existing),entry_capacity_demand(db,existing))
    occupied=sum(logical.values())
    if occupied+demand>capacity:
     raise HTTPException(409,f"{laboratory.laboratory_name} {laboratory.room_number} has capacity {capacity}. Existing occupancy is {occupied} students during period {period}; the selected {demand}-student group cannot be added.")

 def _validate_lab_lunch(self,db,term_id,start,length):
  term=db.scalar(select(AcademicTerm).where(AcademicTerm.id==term_id));schedule_type="FIRST_YEAR" if term and term.year_number==1 else "HIGHER_YEAR"
  timings=list(db.scalars(select(PeriodTiming).where(PeriodTiming.schedule_type==schedule_type,PeriodTiming.is_active.is_(True)).order_by(PeriodTiming.sequence_number)))
  lunch=next((timing.sequence_number for timing in timings if not timing.is_instructional and timing.break_type=="LUNCH"),None)
  positions={timing.period_number:timing.sequence_number for timing in timings if timing.is_instructional}
  end=start+length-1
  if lunch is not None and positions.get(start,0)<lunch<positions.get(end,10**9):raise HTTPException(422,"Laboratory session must not cross lunch")

 def create(self,db,version_id,data,user_id=None):
  if data.combined_teaching_event_id:raise HTTPException(409,"Combined teaching children are created through the solver and managed atomically")
  self._validate(db,version_id,data);now=datetime.now(timezone.utc);entry=TimetableEntry(timetable_version_id=version_id,**data.model_dump(),created_at=now,updated_at=now);db.add(entry);db.flush();self._audit(db,entry,"CREATED",user_id,None,self._values(entry));db.commit();db.refresh(entry);return entry
 def update(self,db,entry,data,user_id=None):
  if entry.combined_teaching_event_id:raise HTTPException(409,"A combined teaching child cannot be changed independently; move the complete event")
  if entry.laboratory_rotation_block_id:raise HTTPException(409,"A rotation child cannot be changed independently; move or edit the complete rotation block")
  if entry.is_locked:raise HTTPException(409,"Locked timetable entry cannot be updated")
  old=self._values(entry);values={field:getattr(entry,field) for field in TimetableEntryCreate.model_fields};values.update(data.model_dump(exclude_unset=True))
  try:validated=TimetableEntryCreate(**values)
  except ValidationError as error:raise HTTPException(422,"Updated timetable entry is invalid") from error
  self._validate(db,entry.timetable_version_id,validated,entry.id)
  for key,value in data.model_dump(exclude_unset=True).items():setattr(entry,key,value)
  entry.updated_at=datetime.now(timezone.utc);self._audit(db,entry,"UPDATED",user_id,old,self._values(entry));db.commit();db.refresh(entry);return entry
 def delete(self,db,entry,user_id=None):
  if entry.combined_teaching_event_id:raise HTTPException(409,"A combined teaching child cannot be deleted independently; edit the combined teaching group")
  if entry.laboratory_rotation_block_id:raise HTTPException(409,"A rotation child cannot be deleted independently; edit the complete rotation block")
  if entry.is_locked:raise HTTPException(409,"Locked timetable entry cannot be deleted")
  self._version_context(db,entry.timetable_version_id);self._audit(db,entry,"DELETED",user_id,self._values(entry),None);db.flush();db.delete(entry);db.commit()
 def replace_generated(self,db,version_id,payloads):
  self._version_context(db,version_id);entries=[];now=datetime.now(timezone.utc)
  try:
   entry_repository.remove_replaceable_generated(db,version_id)
   for payload in payloads:
    self._validate(db,version_id,payload);values=payload.model_dump();values["is_manual"]=False;entry=TimetableEntry(timetable_version_id=version_id,**values,created_at=now,updated_at=now);db.add(entry);db.flush();entries.append(entry)
   db.commit();return entries
  except Exception:
   db.rollback();raise

entry_service=TimetableEntryService()
