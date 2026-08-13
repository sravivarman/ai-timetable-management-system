"""Phase 1 OR-Tools CP-SAT solver service and endpoint integration tests."""
import os
import copy
import unittest
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from uuid import UUID
from uuid import uuid4

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")

from sqlalchemy import select
from app.modules.authentication.models import Permission,Role
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.facilities.models import Laboratory
from app.modules.resource_availability.models import ResourceAvailabilitySlot
from app.modules.course_offerings.models import CourseOffering, CourseOfferingAllowedLaboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.faculty_scheduling.models import FacultyAvailability
from app.modules.laboratory_batches.models import LaboratoryBatchConfiguration,StudentBatch
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.sections.models import Section
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetable_validation.schemas import ValidationRunRequest
from app.modules.timetable_validation.service import validate as validate_prerequisites
from app.modules.timetables.models import SolverRun,Timetable,TimetableEntry,TimetableVersion
from app.modules.timetables.service import solver_input_builder
from app.modules.timetables.solver_service import solver_service
from tests import test_solver_input_builder as solver_support

class TimetableSolverTests(unittest.TestCase):
 def setUp(self):
  self.fixture=solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready");self.fixture.setUp();self.ctx=self.fixture.ctx;self.client=self.fixture.client
  db=self.ctx.session_factory()
  try:
   permissions=[Permission(resource="timetable_solver",action="read"),Permission(resource="timetable_solver",action="run")];db.add_all(permissions);db.flush();roles={role.name:role for role in db.scalars(select(Role)).all()};roles["Administrator"].permissions.extend(permissions);roles["Timetable Coordinator"].permissions.extend(permissions);roles["HOD"].permissions.append(permissions[0]);db.commit()
  finally:db.close()
  self.build_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input";self.solve_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/solve"
 def tearDown(self):self.fixture.tearDown()
 def build(self):
  response=self.client.post(self.build_url,headers=self.ctx.headers["administrator"]);self.assertEqual(response.status_code,201,response.text);return response
 def solve(self,role="administrator",**payload):return self.client.post(self.solve_url,json={"time_limit_seconds":10,"random_seed":1}|payload,headers=self.ctx.headers[role])

 def test_feasible_schedule_is_complete_and_respects_hard_constraints(self):
  self.build();response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"});self.assertEqual(response.json()["generated_entry_count"],10)
  db=self.ctx.session_factory()
  try:
   entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id)));self.assertEqual(len(entries),10)
   counts=Counter(entry.course_offering_id for entry in entries);self.assertEqual(counts[self.fixture.theory_offering.id],4);self.assertEqual(counts[self.fixture.lab_offering.id],6)
   occupied=defaultdict(list);faculty_daily=Counter();labs_daily=Counter();theory_daily=defaultdict(list)
   for entry in entries:
    for period in range(entry.period_number,entry.period_number+entry.session_length):
     if entry.faculty_id:occupied[("faculty",entry.faculty_id,entry.working_day_id,period)].append(entry.id)
     if entry.classroom_id:occupied[("classroom",entry.classroom_id,entry.working_day_id,period)].append(entry.id)
     if entry.laboratory_id:occupied[("laboratory",entry.laboratory_id,entry.working_day_id,period)].append(entry.id)
     if entry.student_batch_id:occupied[("batch",entry.student_batch_id,entry.working_day_id,period)].append(entry.id)
     if entry.faculty_id:faculty_daily[(entry.faculty_id,entry.working_day_id)]+=1
    if entry.entry_type=="LABORATORY":labs_daily[(entry.section_id,entry.working_day_id)]+=1;self.assertFalse(entry.period_number<=3<entry.period_number+entry.session_length-1)
    if entry.entry_type=="THEORY":theory_daily[(entry.course_offering_id,entry.working_day_id)].append(entry.period_number)
   self.assertTrue(all(len(ids)==1 for ids in occupied.values()));self.assertTrue(all(value<=5 for value in faculty_daily.values()));self.assertTrue(all(value<=1 for value in labs_daily.values()));self.assertTrue(all(len(periods)<=2 and all(abs(a-b)>1 for index,a in enumerate(periods) for b in periods[index+1:]) for periods in theory_daily.values()))
   monday_blocked=[entry for entry in entries if entry.entry_type=="LABORATORY" and entry.working_day_id==self.fixture.working_day.id and entry.period_number<=7<entry.period_number+entry.session_length];self.assertFalse(monday_blocked)
   self.assertEqual(db.get(TimetableVersion,self.fixture.version.id).solver_status,response.json()["status"]);self.assertEqual(db.get(Timetable,self.fixture.timetable.id).status,"GENERATED")
  finally:db.close()

 def test_preferred_laboratory_falls_back_and_fixed_override_is_hard(self):
  db=self.ctx.session_factory()
  try:
   second=Laboratory(laboratory_code="TST-LAB-2",laboratory_name="Alternative Laboratory",room_number="T-202",owning_department_id=self.ctx.active_department.id,availability_mode="EXCEPT_BLOCKED")
   db.add(second);db.flush()
   db.add_all([CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=self.fixture.laboratory.id,preference_priority=1),CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=second.id,preference_priority=2)])
   offering=db.get(CourseOffering,self.fixture.lab_offering.id);offering.laboratory_selection_mode="PREFERRED";offering.laboratory_override_id=self.fixture.laboratory.id
   existing={(slot.working_day_id,slot.period_number) for slot in db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type=="LABORATORY",ResourceAvailabilitySlot.resource_id==self.fixture.laboratory.id,ResourceAvailabilitySlot.academic_term_id==self.fixture.term.id))}
   for day in db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))):
    for period in range(1,8):
     if (day.id,period) not in existing:db.add(ResourceAvailabilitySlot(resource_type="LABORATORY",resource_id=self.fixture.laboratory.id,academic_term_id=self.fixture.term.id,working_day_id=day.id,period_number=period,availability_type="BLOCKED"))
   db.commit();second_id=second.id
  finally:db.close()
  snapshot=self.build().json()["snapshot_json"];offering_snapshot=next(item for item in snapshot["course_offerings"] if item["id"]==str(self.fixture.lab_offering.id))
  self.assertEqual(offering_snapshot["laboratory_selection_mode"],"PREFERRED");self.assertEqual(set(offering_snapshot["eligible_laboratory_ids"]),{str(self.fixture.laboratory.id),str(second_id)});self.assertEqual(offering_snapshot["preferred_laboratory_id"],str(self.fixture.laboratory.id))
  response=self.solve();self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"},response.text)
  db=self.ctx.session_factory()
  try:
   labs={entry.laboratory_id for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.course_offering_id==self.fixture.lab_offering.id))};self.assertEqual(labs,{second_id})
   offering=db.get(CourseOffering,self.fixture.lab_offering.id);offering.laboratory_selection_mode="FIXED";offering.laboratory_override_id=second_id;db.commit()
  finally:db.close()
  fixed_snapshot=self.build().json()["snapshot_json"];fixed=next(item for item in fixed_snapshot["course_offerings"] if item["id"]==str(self.fixture.lab_offering.id));self.assertEqual(fixed["eligible_laboratory_ids"],[str(second_id)]);self.assertEqual(fixed["fixed_laboratory_id"],str(second_id))
  db=self.ctx.session_factory()
  try:
   for day in db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))):
    for period in range(1,8):db.add(ResourceAvailabilitySlot(resource_type="LABORATORY",resource_id=second_id,academic_term_id=self.fixture.term.id,working_day_id=day.id,period_number=period,availability_type="BLOCKED"))
   db.commit()
  finally:db.close()
  self.build()
  response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertEqual(response.json()["status"],"INFEASIBLE")

 def test_restricted_offering_snapshot_and_solver_never_use_course_level_fallback(self):
  db=self.ctx.session_factory()
  try:
   allowed=Laboratory(laboratory_code="TST-ALLOWED",laboratory_name="Allowed Physics Laboratory",room_number="T-203",owning_department_id=self.ctx.active_department.id)
   excluded=Laboratory(laboratory_code="TST-EXCLUDED",laboratory_name="Excluded Physics Laboratory",room_number="T-204",owning_department_id=self.ctx.active_department.id)
   db.add_all([allowed,excluded]);db.flush()
   db.add_all([
    CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=self.fixture.laboratory.id,preference_priority=1),
    CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=allowed.id,preference_priority=2),
    CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=excluded.id,preference_priority=3),
   ])
   offering=db.get(CourseOffering,self.fixture.lab_offering.id);offering.laboratory_selection_mode="RESTRICTED";offering.laboratory_override_id=None
   db.add_all([
    CourseOfferingAllowedLaboratory(course_offering_id=offering.id,laboratory_id=self.fixture.laboratory.id,preference_priority=1),
    CourseOfferingAllowedLaboratory(course_offering_id=offering.id,laboratory_id=allowed.id,preference_priority=2),
   ])
   existing={(slot.working_day_id,slot.period_number) for slot in db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type=="LABORATORY",ResourceAvailabilitySlot.resource_id==self.fixture.laboratory.id,ResourceAvailabilitySlot.academic_term_id==self.fixture.term.id))}
   for day in db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))):
    for period in range(1,8):
     if (day.id,period) not in existing:db.add(ResourceAvailabilitySlot(resource_type="LABORATORY",resource_id=self.fixture.laboratory.id,academic_term_id=self.fixture.term.id,working_day_id=day.id,period_number=period,availability_type="BLOCKED"))
   db.commit();allowed_id=allowed.id;excluded_id=excluded.id
  finally:db.close()
  first=self.build().json();second=self.build().json();self.assertEqual((first["id"],first["input_hash"]),(second["id"],second["input_hash"]))
  item=next(value for value in first["snapshot_json"]["course_offerings"] if value["id"]==str(self.fixture.lab_offering.id))
  self.assertEqual(item["laboratory_selection_mode"],"RESTRICTED");self.assertEqual(item["allowed_laboratory_ids"],[str(self.fixture.laboratory.id),str(allowed_id)]);self.assertEqual(set(item["eligible_laboratory_ids"]),{str(self.fixture.laboratory.id),str(allowed_id)});self.assertNotIn(str(excluded_id),item["eligible_laboratory_ids"])
  response=self.solve();self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"},response.text)
  db=self.ctx.session_factory()
  try:
   used={entry.laboratory_id for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.course_offering_id==self.fixture.lab_offering.id))};self.assertEqual(used,{allowed_id});self.assertNotIn(excluded_id,used)
  finally:db.close()

 def test_two_sections_use_two_eligible_laboratories_simultaneously(self):
  db=self.ctx.session_factory()
  try:
   program_id=self.fixture.section.program_id
   self.fixture.theory_offering.is_active=False;db.merge(self.fixture.theory_offering)
   self.fixture.lab_course.lab_sessions_per_week=1;db.merge(self.fixture.lab_course)
   for batch in db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id).order_by(StudentBatch.sequence_number)):
    batch.is_active=batch.sequence_number==1
   db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id==self.fixture.lab_offering.id)).number_of_groups=1
   second_lab=Laboratory(laboratory_code="TST-LAB-2",laboratory_name="Second Eligible Laboratory",room_number="T-202",owning_department_id=self.ctx.active_department.id)
   second_section=Section(program_id=program_id,academic_term_id=self.fixture.term.id,section_name="B",section_code="TST-B",student_strength=72)
   second_faculty=Faculty(faculty_code="TST002",full_name="Second Faculty",department_id=self.ctx.active_department.id,designation="Assistant Professor",institutional_email="solver.faculty.2@vce.ac.in",minimum_weekly_workload=0,maximum_weekly_workload=18,maximum_periods_per_day=5)
   db.add_all([second_lab,second_section,second_faculty]);db.flush()
   db.add_all([CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=self.fixture.laboratory.id,preference_priority=1),CourseEligibleLaboratory(course_id=self.fixture.lab_course.id,laboratory_id=second_lab.id,preference_priority=2)])
   second_offering=CourseOffering(course_id=self.fixture.lab_course.id,section_id=second_section.id,academic_term_id=self.fixture.term.id)
   db.add(second_offering);db.flush()
   db.add_all([LaboratoryFacultyAllocation(course_offering_id=second_offering.id,faculty_id=second_faculty.id,role_type="MAIN"),StudentBatch(section_id=second_section.id,batch_name="B1",sequence_number=1,roll_number_start=1,roll_number_end=72,student_count=72),LaboratoryBatchConfiguration(course_offering_id=second_offering.id,section_id=second_section.id,number_of_groups=1)])
   days=list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))))
   for faculty_id in (self.fixture.faculty.id,second_faculty.id):
    for day in days:
     for period in range(1,8):
      if day.day_name!="Monday" or period not in (1,2):db.add(FacultyAvailability(faculty_id=faculty_id,academic_term_id=self.fixture.term.id,day_of_week=day.day_name,period_number=period,availability_type="unavailable"))
   run=db.get(ValidationRun,self.fixture.run.id);run.scope_type="PROGRAM";run.section_id=None;run.program_id=program_id
   timetable=db.get(Timetable,self.fixture.timetable.id);timetable.scope_type="PROGRAM";timetable.section_id=None;timetable.program_id=program_id
   db.commit();second_section_id=second_section.id
  finally:db.close()
  self.build();response=self.solve();self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"},response.text)
  db=self.ctx.session_factory()
  try:
   entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.entry_type=="LABORATORY",TimetableEntry.timetable_version_id==self.fixture.version.id)))
   self.assertEqual({entry.section_id for entry in entries},{self.fixture.section.id,second_section_id});self.assertEqual(len({(entry.working_day_id,entry.period_number) for entry in entries}),1);self.assertEqual(len({entry.laboratory_id for entry in entries}),2)
  finally:db.close()

 def test_grouped_multi_period_practical_uses_primary_classroom_without_rotation_or_lab(self):
  db=self.ctx.session_factory()
  try:
   self.fixture.lab_offering.is_active=False
   db.merge(self.fixture.lab_offering)
   batches=list(db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id).order_by(StudentBatch.sequence_number)))
   batches[-1].is_active=False
   practical=Course(course_code="CCDT",course_name="Community Centered Design Thinking",offering_department_id=self.ctx.active_department.id,course_type="PRACTICAL",weekly_periods=3,grouping_mode="GROUPED",default_group_count=2,session_duration=3,sessions_per_week=1,venue_requirement="CLASSROOM_ONLY",counts_toward_workload=True)
   db.add(practical);db.flush()
   offering=CourseOffering(course_id=practical.id,section_id=self.fixture.section.id,academic_term_id=self.fixture.term.id)
   db.add(offering);db.flush()
   db.add_all([LaboratoryFacultyAllocation(course_offering_id=offering.id,faculty_id=self.fixture.faculty.id,role_type="MAIN"),LaboratoryBatchConfiguration(course_offering_id=offering.id,section_id=self.fixture.section.id,number_of_groups=2,is_rotation_enabled=False)])
   db.get(FacultyAvailability,self.fixture.availability.id).availability_type="unavailable"
   for period in range(2,8):db.add(FacultyAvailability(faculty_id=self.fixture.faculty.id,academic_term_id=self.fixture.term.id,day_of_week="Monday",period_number=period,availability_type="unavailable"))
   db.commit();offering_id=offering.id
   issues,_=validate_prerequisites(db,ValidationRunRequest(academic_term_id=self.fixture.term.id,scope_type="SECTION",section_id=self.fixture.section.id))
   self.assertFalse(any(issue["issue_code"]=="LABORATORY_MISSING" and str(issue.get("entity_id"))==str(offering_id) for issue in issues))
   self.assertFalse(any(issue["issue_code"]=="FACULTY_ALLOCATION_MISSING" and str(issue.get("entity_id"))==str(offering_id) for issue in issues))
  finally:db.close()
  snapshot=self.build().json()["snapshot_json"]
  practical_snapshot=next(item for item in snapshot["course_offerings"] if item["id"]==str(offering_id))
  self.assertEqual(practical_snapshot["grouping_mode"],"GROUPED");self.assertEqual(practical_snapshot["session_duration"],3);self.assertEqual(practical_snapshot["venue_requirement"],"CLASSROOM_ONLY");self.assertEqual(practical_snapshot["effective_group_count"],2)
  response=self.solve();self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"},response.text)
  db=self.ctx.session_factory()
  try:
   entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.course_offering_id==offering_id)))
   self.assertEqual(len(entries),2);self.assertTrue(all(entry.entry_type=="PRACTICAL" and entry.session_length==3 and entry.classroom_id==self.fixture.classroom.id and entry.laboratory_id is None and entry.laboratory_faculty_allocation_id is not None for entry in entries));self.assertEqual(len({entry.student_batch_id for entry in entries}),2);self.assertTrue(all(entry.laboratory_rotation_block_id is None for entry in entries));self.assertTrue(all(entry.working_day_id!=self.fixture.working_day.id for entry in entries));self.assertNotEqual((entries[0].working_day_id,entries[0].period_number),(entries[1].working_day_id,entries[1].period_number))
  finally:db.close()

 def test_solver_schedules_six_configured_student_groups_without_special_branches(self):
  db=self.ctx.session_factory()
  try:
   for batch in db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id)):batch.is_active=False
   for sequence in range(1,7):
    start=(sequence-1)*12+1;db.add(StudentBatch(section_id=self.fixture.section.id,batch_name=f"A{sequence}",sequence_number=sequence,roll_number_start=start,roll_number_end=start+11,student_count=12))
   db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id==self.fixture.lab_offering.id)).number_of_groups=6
   db.get(Course,self.fixture.lab_course.id).lab_sessions_per_week=1
   db.commit()
  finally:db.close()
  self.build();response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"})
  db=self.ctx.session_factory()
  try:
   entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id,TimetableEntry.entry_type=="LABORATORY")))
   self.assertEqual(len(entries),6);self.assertEqual(len({entry.student_batch_id for entry in entries}),6);self.assertTrue(all(entry.student_batch_id for entry in entries))
  finally:db.close()

 def test_single_group_laboratory_uses_a_real_group_record(self):
  db=self.ctx.session_factory()
  try:
   for batch in db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id)):batch.is_active=False
   group=StudentBatch(section_id=self.fixture.section.id,batch_name="FULL",sequence_number=1,roll_number_start=1,roll_number_end=72,student_count=72);db.add(group)
   db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id==self.fixture.lab_offering.id)).number_of_groups=1
   course=db.get(Course,self.fixture.lab_course.id);course.weekly_periods=3;course.session_duration=course.lab_session_duration=3;course.sessions_per_week=course.lab_sessions_per_week=1
   db.commit();group_id=group.id
  finally:db.close()
  self.build();response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"})
  db=self.ctx.session_factory()
  try:
   entries=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id,TimetableEntry.entry_type=="LABORATORY")))
   self.assertEqual(len(entries),1);self.assertEqual({entry.student_batch_id for entry in entries},{group_id});self.assertEqual(entries[0].session_length,3)
  finally:db.close()

 def test_locked_entry_is_preserved_and_repeated_solve_replaces_generated_only(self):
  now=datetime.now(timezone.utc);db=self.ctx.session_factory()
  try:
   locked=TimetableEntry(timetable_version_id=self.fixture.version.id,course_offering_id=self.fixture.theory_offering.id,section_id=self.fixture.section.id,faculty_id=self.fixture.faculty.id,classroom_id=self.fixture.classroom.id,working_day_id=self.fixture.working_day.id,period_number=1,session_length=1,entry_type="THEORY",is_manual=False,is_locked=True,created_at=now,updated_at=now);db.add(locked);db.commit();locked_id=locked.id
  finally:db.close()
  self.build();first=self.solve();self.assertIn(first.json()["status"],{"FEASIBLE","OPTIMAL"})
  db=self.ctx.session_factory()
  try:first_generated={entry.id for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id,TimetableEntry.is_locked.is_(False)))};self.assertIsNotNone(db.get(TimetableEntry,locked_id))
  finally:db.close()
  second=self.solve();self.assertIn(second.json()["status"],{"FEASIBLE","OPTIMAL"})
  db=self.ctx.session_factory()
  try:
   second_generated={entry.id for entry in db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id,TimetableEntry.is_locked.is_(False)))};self.assertTrue(first_generated.isdisjoint(second_generated));self.assertIsNotNone(db.get(TimetableEntry,locked_id));self.assertEqual(db.scalar(select(SolverRun).where(SolverRun.id==UUID(second.json()["id"]))).status,second.json()["status"])
  finally:db.close()

 def test_stale_snapshot_locked_version_and_failed_validation_are_rejected(self):
  self.build();db=self.ctx.session_factory()
  try:db.get(Course,self.fixture.theory_course.id).weekly_periods=5;db.commit()
  finally:db.close()
  stale=self.solve();self.assertEqual(stale.status_code,409,stale.text);self.assertIn("stale",stale.json()["detail"])
  db=self.ctx.session_factory()
  try:db.get(Course,self.fixture.theory_course.id).weekly_periods=4;db.get(TimetableVersion,self.fixture.version.id).is_locked=True;db.commit()
  finally:db.close()
  self.assertEqual(self.solve().status_code,409)
  db=self.ctx.session_factory()
  try:db.get(TimetableVersion,self.fixture.version.id).is_locked=False;db.get(ValidationRun,self.fixture.run.id).status="FAILED";db.commit()
  finally:db.close()
  failed=self.solve();self.assertEqual(failed.status_code,422,failed.text)

 def test_fully_unavailable_faculty_returns_infeasible_with_statistics(self):
  db=self.ctx.session_factory()
  try:
   existing=db.get(FacultyAvailability,self.fixture.availability.id);existing.availability_type="unavailable";days=list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True))))
   for day in days:
    for period in range(1,8):
     if day.day_name=="Monday" and period==1:continue
     db.add(FacultyAvailability(faculty_id=self.fixture.faculty.id,academic_term_id=self.fixture.term.id,day_of_week=day.day_name,period_number=period,availability_type="unavailable"))
   db.commit()
  finally:db.close()
  self.build();response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertEqual(response.json()["status"],"INFEASIBLE");self.assertEqual(response.json()["generated_entry_count"],0);self.assertGreater(response.json()["statistics_json"]["unit_count"],0);self.assertIn("constraint_count",response.json()["statistics_json"])

 def test_solver_permissions_and_run_retrieval(self):
  self.build();self.assertEqual(self.solve("hod").status_code,403);self.assertEqual(self.solve("unauthorized").status_code,403);run=self.solve("coordinator");self.assertEqual(run.status_code,201,run.text)
  listing=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/solver-runs",headers=self.ctx.headers["hod"]);self.assertEqual(listing.status_code,200,listing.text);self.assertEqual(listing.json()["total"],1)
  detail=self.client.get(f"/api/v1/solver-runs/{run.json()['id']}",headers=self.ctx.headers["hod"]);self.assertEqual(detail.status_code,200,detail.text);self.assertEqual(detail.json()["id"],run.json()["id"])

 def test_solver_run_listing_is_newest_first_with_deterministic_ties(self):
  snapshot=self.build().json();base=datetime(2026,8,3,12,0,tzinfo=timezone.utc);lower=UUID("00000000-0000-0000-0000-000000000001");higher=UUID("00000000-0000-0000-0000-000000000002");older=UUID("00000000-0000-0000-0000-000000000099")
  db=self.ctx.session_factory()
  try:
   common={"timetable_version_id":self.fixture.version.id,"solver_input_snapshot_id":UUID(snapshot["id"]),"started_at":base,"completed_at":base,"generated_entry_count":1,"created_by":self.fixture.run.created_by}
   db.add_all([SolverRun(id=older,status="INFEASIBLE",created_at=base-timedelta(hours=1),**common),SolverRun(id=lower,status="FEASIBLE",created_at=base,**common),SolverRun(id=higher,status="FEASIBLE",created_at=base,**common)]);db.commit()
  finally:db.close()
  url=f"/api/v1/timetable-versions/{self.fixture.version.id}/solver-runs"
  listing=self.client.get(url+"?page=1&page_size=10",headers=self.ctx.headers["hod"]);self.assertEqual(listing.status_code,200,listing.text);self.assertEqual([item["id"] for item in listing.json()["items"]],[str(higher),str(lower),str(older)])
  latest=self.client.get(url+"?page=1&page_size=1",headers=self.ctx.headers["hod"]);self.assertEqual(latest.status_code,200,latest.text);self.assertEqual(latest.json()["items"][0]["id"],str(higher))
  global_url="/api/v1/solver-runs?page=1&page_size=1";global_latest=self.client.get(global_url,headers=self.ctx.headers["hod"]);self.assertEqual(global_latest.status_code,200,global_latest.text);self.assertEqual(global_latest.json()["items"][0]["id"],str(higher))
  status_filter=self.client.get("/api/v1/solver-runs?status=INFEASIBLE&page=1&page_size=10",headers=self.ctx.headers["hod"]);self.assertEqual(status_filter.status_code,200,status_filter.text);self.assertEqual([item["id"] for item in status_filter.json()["items"]],[str(older)])
  version_filter=self.client.get(f"/api/v1/solver-runs?timetable_version_id={self.fixture.version.id}&page=1&page_size=10",headers=self.ctx.headers["hod"]);self.assertEqual(version_filter.json()["total"],3)
  empty_filter=self.client.get("/api/v1/solver-runs?timetable_version_id=00000000-0000-0000-0000-000000000000",headers=self.ctx.headers["hod"]);self.assertEqual(empty_filter.json()["total"],0)
  self.assertEqual(self.client.get(global_url,headers=self.ctx.headers["unauthorized"]).status_code,403)

 def test_warning_validation_run_is_solver_eligible(self):
  db=self.ctx.session_factory()
  try:db.get(ValidationRun,self.fixture.run.id).status="WARNING";db.commit()
  finally:db.close()
  self.build();response=self.solve();self.assertEqual(response.status_code,201,response.text);self.assertIn(response.json()["status"],{"FEASIBLE","OPTIMAL"})

 def test_laboratory_can_cross_short_break_but_not_lunch(self):
  snapshot=self.build().json()["snapshot_json"]
  lab_only=copy.deepcopy(snapshot);lab_only["course_offerings"]=[item for item in lab_only["course_offerings"] if item["course_type"]=="LABORATORY"];lab_only["theory_faculty_allocations"]=[]
  faculty_id=lab_only["laboratory_faculty_allocations"][0]["faculty_id"]
  lab_only["faculty_availability"]=[{"faculty_id":faculty_id,"day_of_week":day["day_name"],"period_number":period,"availability_type":"unavailable"} for day in lab_only["working_days"] for period in range(1,8) if period not in {5,6}]
  db=self.ctx.session_factory()
  try:
   short_break=solver_service._solve_snapshot(db,lab_only,self.fixture.version.id,10,1);self.assertIn(short_break["status"],{"FEASIBLE","OPTIMAL"});self.assertTrue(all(entry["period_number"]==5 for entry in short_break["entries"]))
   lunch_only=copy.deepcopy(lab_only);lunch_only["faculty_availability"]=[{"faculty_id":faculty_id,"day_of_week":day["day_name"],"period_number":period,"availability_type":"unavailable"} for day in lunch_only["working_days"] for period in range(1,8) if period not in {3,4}]
   lunch=solver_service._solve_snapshot(db,lunch_only,self.fixture.version.id,10,1);self.assertEqual(lunch["status"],"INFEASIBLE")
  finally:db.close()

 def test_laboratory_only_selected_periods_are_hard_solver_constraints(self):
  snapshot=self.build().json()["snapshot_json"]
  laboratory=snapshot["laboratories"][0];laboratory["availability_mode"]="ONLY_SELECTED";laboratory["is_available_all_periods"]=False
  snapshot["laboratory_availability_blocks"]=[{"laboratory_id":laboratory["id"],"academic_term_id":str(self.fixture.term.id),"working_day_id":day["id"],"period_number":period,"availability_type":"ALLOWED","is_active":True} for day in snapshot["working_days"] for period in (5,6)]
  db=self.ctx.session_factory()
  try:result=solver_service._solve_snapshot(db,snapshot,self.fixture.version.id,10,1)
  finally:db.close()
  self.assertIn(result["status"],{"FEASIBLE","OPTIMAL"});lab_entries=[entry for entry in result["entries"] if entry["entry_type"]=="LABORATORY"];self.assertTrue(lab_entries);self.assertTrue(all(entry["period_number"]==5 for entry in lab_entries))

 def test_phase2_quality_endpoint_and_objective_breakdown(self):
  self.build();response=self.solve(optimization_profile="BALANCED");self.assertEqual(response.status_code,201,response.text);body=response.json();statistics=body["statistics_json"]
  self.assertEqual(statistics["optimization_profile"],"BALANCED");self.assertEqual(statistics["deterministic_seed"],1);self.assertGreater(statistics["soft_constraint_count"],0);self.assertGreater(statistics["hard_constraint_count"],0)
  expected={"theory_distribution_penalty","adjacency_penalty","section_gap_penalty","faculty_gap_penalty","preference_penalty","first_last_fairness_penalty","faculty_load_balance_penalty","section_load_balance_penalty","room_change_penalty","laboratory_placement_penalty"};self.assertEqual(set(statistics["objective_breakdown"]),expected);self.assertAlmostEqual(statistics["total_penalty"],sum(statistics["objective_breakdown"].values()));self.assertGreaterEqual(statistics["solution_quality_score"],0);self.assertLessEqual(statistics["solution_quality_score"],100)
  quality=self.client.get(f"/api/v1/solver-runs/{body['id']}/quality",headers=self.ctx.headers["hod"]);self.assertEqual(quality.status_code,200,quality.text);metrics=quality.json();self.assertEqual(metrics["total_penalty"],statistics["total_penalty"]);self.assertEqual(metrics["objective_breakdown"],statistics["objective_breakdown"]);self.assertIn(str(self.fixture.faculty.id),metrics["faculty_daily_loads"]);self.assertEqual(metrics["section_idle_gap_counts"][str(self.fixture.section.id)],0)
  forbidden=self.client.get(f"/api/v1/solver-runs/{body['id']}/quality",headers=self.ctx.headers["unauthorized"]);self.assertEqual(forbidden.status_code,403)

 def test_phase2_distribution_and_determinism(self):
  self.build();first=self.solve();self.assertIn(first.json()["status"],{"FEASIBLE","OPTIMAL"})
  def placements():
   db=self.ctx.session_factory()
   try:return sorted((str(item.course_offering_id),str(item.working_day_id),item.period_number,item.session_length,str(item.student_batch_id or "")) for item in db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id,TimetableEntry.is_locked.is_(False))))
   finally:db.close()
  first_placements=placements();first_breakdown=first.json()["statistics_json"]["objective_breakdown"];second=self.solve();self.assertIn(second.json()["status"],{"FEASIBLE","OPTIMAL"});self.assertEqual(placements(),first_placements);self.assertEqual(second.json()["statistics_json"]["objective_breakdown"],first_breakdown)
  theory_days=Counter(day for offering,day,period,length,batch in first_placements if offering==str(self.fixture.theory_offering.id));self.assertEqual(sorted(theory_days.values()),[1,1,1,1]);lab_days=Counter(day for offering,day,period,length,batch in first_placements if offering==str(self.fixture.lab_offering.id));self.assertTrue(all(value==1 for value in lab_days.values()))

 def test_phase2_profiles_and_weight_validation(self):
  self.build();unknown=self.solve(weight_overrides={"not_a_constraint":1});self.assertEqual(unknown.status_code,422,unknown.text);negative=self.solve(weight_overrides={"faculty_idle_gap":-1});self.assertEqual(negative.status_code,422,negative.text)
  fast=self.client.post(self.solve_url,json={"optimization_profile":"FAST","random_seed":1},headers=self.ctx.headers["administrator"]);self.assertEqual(fast.status_code,201,fast.text);self.assertEqual(fast.json()["statistics_json"]["configured_time_limit_seconds"],15)
  balanced=self.solve(optimization_profile="BALANCED");quality=self.client.post(self.solve_url,json={"optimization_profile":"QUALITY","random_seed":1,"time_limit_seconds":10},headers=self.ctx.headers["administrator"]);self.assertEqual(quality.status_code,201,quality.text);self.assertLessEqual(quality.json()["statistics_json"]["total_penalty"],balanced.json()["statistics_json"]["total_penalty"])

 def test_supporting_faculty_alternative_is_selected_by_cp_sat(self):
  snapshot=self.build().json()["snapshot_json"];support_a=str(uuid4());support_b=str(uuid4());template=copy.deepcopy(snapshot["faculty"][0]);faculty_a=copy.deepcopy(template);faculty_b=copy.deepcopy(template);faculty_a.update({"id":support_a,"faculty_code":"ALT-A"});faculty_b.update({"id":support_b,"faculty_code":"ALT-B"});snapshot["faculty"].extend([faculty_a,faculty_b])
  allocation_template={"course_offering_id":str(self.fixture.lab_offering.id),"role_type":"SUPPORTING","required_with_main_faculty_id":None,"alternative_group_code":"ALT-GROUP","minimum_sessions_per_week":2,"maximum_sessions_per_week":2,"is_active":True}
  first=allocation_template|{"id":str(uuid4()),"faculty_id":support_a};second=allocation_template|{"id":str(uuid4()),"faculty_id":support_b};snapshot["laboratory_faculty_allocations"].extend([first,second])
  snapshot["faculty_availability"].extend({"faculty_id":support_a,"day_of_week":day["day_name"],"period_number":period,"availability_type":"unavailable"} for day in snapshot["working_days"] for period in range(1,8))
  db=self.ctx.session_factory()
  try:result=solver_service._solve_snapshot(db,snapshot,self.fixture.version.id,10,1)
  finally:db.close()
  self.assertIn(result["status"],{"FEASIBLE","OPTIMAL"});selections=result["statistics"]["selected_supporting_faculty"];self.assertTrue(selections);self.assertTrue(all(item["faculty_ids"]==[support_b] for item in selections))

if __name__=="__main__":unittest.main()
