"""Phase 3 timetable review, adjustment, comparison, workflow, and report tests."""
import os
import unittest
from datetime import datetime,timezone
from uuid import UUID
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from sqlalchemy import select
from app.core.security import create_access_token,hash_password
from app.modules.authentication.models import Permission,Role,User
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.faculty_scheduling.models import FacultyAvailability
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.timetables.models import Timetable,TimetableEntry,TimetableEntryAudit,TimetableStatusHistory,TimetableVersion
from tests import test_solver_input_builder as solver_support

class TimetableReviewEndpointTests(unittest.TestCase):
 def setUp(self):
  self.fixture=solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready");self.fixture.setUp();self.ctx=self.fixture.ctx;self.client=self.fixture.client
  db=self.ctx.session_factory()
  try:
   keys=(("timetable_entries","read"),("timetable_entries","manage"),("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_versions","copy"),("timetable_workflow","review"),("timetable_workflow","approve"),("timetable_workflow","publish"),("timetable_workflow","archive"),("timetable_audit","read"));permissions={key:Permission(resource=key[0],action=key[1]) for key in keys};db.add_all(permissions.values());db.flush();roles={role.name:role for role in db.scalars(select(Role)).all()};admin=roles["Administrator"];coordinator=roles["Timetable Coordinator"];hod=roles["HOD"];faculty_role=roles["Faculty"]
   admin.permissions.extend(permissions.values());coordinator.permissions.extend(permissions[key] for key in (("timetable_entries","read"),("timetable_entries","manage"),("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_versions","copy"),("timetable_workflow","review"),("timetable_audit","read")));hod.permissions.extend(permissions[key] for key in (("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_audit","read")))
   dean=Role(name="Dean",permissions=[permissions[("timetable_views","read")],permissions[("timetable_workflow","approve")],permissions[("timetable_audit","read")]]);principal=Role(name="Principal",permissions=[permissions[("timetable_views","read")],permissions[("timetable_workflow","approve")],permissions[("timetable_workflow","publish")],permissions[("timetable_audit","read")]]);student=Role(name="Student",permissions=[permissions[("timetable_views","read")]]);db.add_all([dean,principal,student]);db.flush()
   users={"dean":User(email="dean.review@vce.ac.in",full_name="Dean",password_hash=hash_password("Password123"),roles=[dean]),"principal":User(email="principal.review@vce.ac.in",full_name="Principal",password_hash=hash_password("Password123"),roles=[principal]),"student":User(email="student.review@vce.ac.in",full_name="Student",password_hash=hash_password("Password123"),roles=[student])};db.add_all(users.values());db.flush()
   hod_user=db.scalar(select(User).where(User.email=="hod.test@vce.ac.in"));faculty_user=db.scalar(select(User).where(User.email=="faculty.test@vce.ac.in"));db.get(Faculty,self.fixture.faculty.id).user_id=faculty_user.id;db.add(Faculty(faculty_code="HOD-TST",full_name="Test HOD",department_id=self.ctx.active_department.id,designation="Professor",institutional_email="hod.faculty@vce.ac.in",user_id=hod_user.id,minimum_weekly_workload=0,maximum_weekly_workload=18));db.get(Timetable,self.fixture.timetable.id).status="GENERATED";db.commit()
   for name,user in users.items():self.ctx.headers[name]={"Authorization":f"Bearer {create_access_token(user.id,user.token_version)}"}
  finally:db.close()
  self.entries_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/entries"
  db=self.ctx.session_factory()
  try:self.lab_allocation=db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id==self.fixture.lab_offering.id));self.batch=db.scalar(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id,StudentBatch.sequence_number==1));self.tuesday=db.scalar(select(WorkingDay).where(WorkingDay.day_name=="Tuesday"))
  finally:db.close()
 def tearDown(self):self.fixture.tearDown()
 def theory(self,period=1,day=None,**changes):
  value={"course_offering_id":str(self.fixture.theory_offering.id),"section_id":str(self.fixture.section.id),"faculty_id":str(self.fixture.faculty.id),"classroom_id":str(self.fixture.classroom.id),"working_day_id":str(day or self.fixture.working_day.id),"period_number":period,"session_length":1,"entry_type":"THEORY","is_manual":False};value.update(changes);return value
 def lab(self,period=5,day=None,**changes):
  value={"course_offering_id":str(self.fixture.lab_offering.id),"section_id":str(self.fixture.section.id),"laboratory_faculty_allocation_id":str(self.lab_allocation.id),"laboratory_id":str(self.fixture.laboratory.id),"student_batch_id":str(self.batch.id),"working_day_id":str(day or self.fixture.working_day.id),"period_number":period,"session_length":2,"entry_type":"LABORATORY","is_manual":False};value.update(changes);return value
 def create(self,payload):
  response=self.client.post(self.entries_url,json=payload,headers=self.ctx.headers["administrator"]);self.assertEqual(response.status_code,201,response.text);return response.json()

 def test_all_visual_views_render_readable_multi_period_entries(self):
  theory=self.create(self.theory());lab=self.create(self.lab())
  paths=(("section",self.fixture.section.id),("faculty",self.fixture.faculty.id),("classroom",self.fixture.classroom.id),("laboratory",self.fixture.laboratory.id),("batch",self.batch.id))
  for kind,resource in paths:
   response=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/views/{kind}/{resource}",headers=self.ctx.headers["administrator"]);self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()["view_type"],kind)
  section=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/views/section/{self.fixture.section.id}",headers=self.ctx.headers["administrator"]).json();rendered=[entry for day in section["days"] for entry in day["entries"]];self.assertEqual({x["course_code"] for x in rendered},{"A-THEORY","Z-LAB"});laboratory=next(x for x in rendered if x["course_type"]=="LABORATORY");self.assertEqual(laboratory["period_numbers"],[5,6]);self.assertEqual(laboratory["session_length"],2);self.assertIsNotNone(laboratory["laboratory_name"])

 def test_manual_move_validation_lock_unlock_and_audit(self):
  entry=self.create(self.theory());moved=self.client.post(f"/api/v1/timetable-entries/{entry['id']}/move",json={"working_day_id":str(self.tuesday.id),"period_number":3,"lock_after_move":False},headers=self.ctx.headers["coordinator"]);self.assertEqual(moved.status_code,200,moved.text);self.assertTrue(moved.json()["is_manual"]);self.assertFalse(moved.json()["is_locked"])
  locked=self.client.post(f"/api/v1/timetable-entries/{entry['id']}/lock",json={"reason":"reviewed"},headers=self.ctx.headers["hod"]);self.assertEqual(locked.status_code,200,locked.text);self.assertEqual(self.client.post(f"/api/v1/timetable-entries/{entry['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":2,"lock_after_move":True},headers=self.ctx.headers["administrator"]).status_code,409)
  self.assertEqual(self.client.post(f"/api/v1/timetable-entries/{entry['id']}/unlock",json={},headers=self.ctx.headers["administrator"]).status_code,422);unlocked=self.client.post(f"/api/v1/timetable-entries/{entry['id']}/unlock",json={"reason":"needs adjustment"},headers=self.ctx.headers["administrator"]);self.assertEqual(unlocked.status_code,200,unlocked.text)
  audit=self.client.get(f"/api/v1/timetable-entries/{entry['id']}/audit",headers=self.ctx.headers["hod"]);self.assertEqual(audit.status_code,200,audit.text);self.assertEqual([x["action_type"] for x in audit.json()],["CREATED","MOVED","LOCKED","UNLOCKED"])
  db=self.ctx.session_factory()
  try:self.assertEqual(db.get(TimetableVersion,self.fixture.version.id).solver_status,"STALE")
  finally:db.close()

 def test_move_rejects_conflict_lunch_unavailability_and_lab_block(self):
  first=self.create(self.theory(period=2));second=self.create(self.theory(period=3,day=self.tuesday.id));conflict=self.client.post(f"/api/v1/timetable-entries/{second['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":2,"lock_after_move":False},headers=self.ctx.headers["administrator"]);self.assertEqual(conflict.status_code,409,conflict.text)
  lab=self.create(self.lab());lunch=self.client.post(f"/api/v1/timetable-entries/{lab['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":3,"lock_after_move":False},headers=self.ctx.headers["administrator"]);self.assertEqual(lunch.status_code,422,lunch.text);blocked=self.client.post(f"/api/v1/timetable-entries/{lab['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":6,"lock_after_move":False},headers=self.ctx.headers["administrator"]);self.assertEqual(blocked.status_code,409,blocked.text)
  db=self.ctx.session_factory()
  try:availability=db.get(FacultyAvailability,self.fixture.availability.id);availability.availability_type="unavailable";db.commit()
  finally:db.close()
  unavailable=self.client.post(f"/api/v1/timetable-entries/{second['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":1,"lock_after_move":False},headers=self.ctx.headers["administrator"]);self.assertEqual(unavailable.status_code,409,unavailable.text)

 def test_version_copy_active_switch_and_semantic_comparison(self):
  self.create(self.theory());copied=self.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/copy",json={"version_name":"Review Copy","source_type":"MANUAL_COPY"},headers=self.ctx.headers["coordinator"]);self.assertEqual(copied.status_code,201,copied.text);copy_id=UUID(copied.json()["id"]);self.assertEqual(copied.json()["version_number"],2);self.assertEqual(copied.json()["solver_status"],"NOT_STARTED")
  db=self.ctx.session_factory()
  try:self.assertFalse(db.get(TimetableVersion,self.fixture.version.id).is_active);self.assertEqual(db.get(Timetable,self.fixture.timetable.id).active_version_id,copy_id);entry=db.scalar(select(TimetableEntry).where(TimetableEntry.timetable_version_id==copy_id));entry.period_number=2;db.commit()
  finally:db.close()
  comparison=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/compare/{copy_id}",headers=self.ctx.headers["administrator"]);self.assertEqual(comparison.status_code,200,comparison.text);self.assertEqual(comparison.json()["summary"]["moved"],1)

 def test_workflow_transitions_history_and_published_immutability(self):
  entry=self.create(self.theory());base=f"/api/v1/timetables/{self.fixture.timetable.id}"
  self.assertEqual(self.client.post(base+"/approve",json={},headers=self.ctx.headers["dean"]).status_code,409)
  review=self.client.post(base+"/submit-review",json={},headers=self.ctx.headers["coordinator"]);self.assertEqual(review.status_code,200,review.text);approved=self.client.post(base+"/approve",json={},headers=self.ctx.headers["dean"]);self.assertEqual(approved.status_code,200,approved.text);published=self.client.post(base+"/publish",json={},headers=self.ctx.headers["principal"]);self.assertEqual(published.status_code,200,published.text)
  move=self.client.post(f"/api/v1/timetable-entries/{entry['id']}/move",json={"working_day_id":str(self.tuesday.id),"period_number":2,"lock_after_move":False},headers=self.ctx.headers["administrator"]);self.assertEqual(move.status_code,409)
  archived=self.client.post(base+"/archive",json={},headers=self.ctx.headers["administrator"]);self.assertEqual(archived.status_code,200,archived.text);history=self.client.get(base+"/status-history",headers=self.ctx.headers["administrator"]);self.assertEqual(history.status_code,200,history.text);self.assertEqual([x["to_status"] for x in history.json()],["UNDER_REVIEW","APPROVED","PUBLISHED","ARCHIVED"])

 def test_free_resources_conflicts_and_student_published_view(self):
  entry=self.create(self.theory());params=f"?working_day_id={self.fixture.working_day.id}&period_number=1"
  faculty=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/free-faculty"+params,headers=self.ctx.headers["administrator"]);rooms=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/free-classrooms"+params,headers=self.ctx.headers["administrator"]);labs=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/free-laboratories"+params,headers=self.ctx.headers["administrator"]);self.assertTrue(all(x.status_code==200 for x in (faculty,rooms,labs)));self.assertNotIn(str(self.fixture.faculty.id),{x["id"] for x in faculty.json()["items"]});self.assertNotIn(str(self.fixture.classroom.id),{x["id"] for x in rooms.json()["items"]})
  db=self.ctx.session_factory()
  try:
   original=db.get(TimetableEntry,UUID(entry["id"]));duplicate=TimetableEntry(timetable_version_id=original.timetable_version_id,course_offering_id=original.course_offering_id,section_id=original.section_id,faculty_id=original.faculty_id,classroom_id=original.classroom_id,working_day_id=original.working_day_id,period_number=original.period_number,session_length=1,entry_type="THEORY",is_manual=True,is_locked=False,created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc));db.add(duplicate);db.commit();db.get(Timetable,self.fixture.timetable.id).status="PUBLISHED";db.commit()
  finally:db.close()
  report=self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/conflicts",headers=self.ctx.headers["administrator"]);self.assertEqual(report.status_code,200,report.text);self.assertGreaterEqual(report.json()["summary"]["total"],3)
  section_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/views/section/{self.fixture.section.id}";self.assertEqual(self.client.get(section_url,headers=self.ctx.headers["student"]).status_code,200);self.assertEqual(self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/views/faculty/{self.fixture.faculty.id}",headers=self.ctx.headers["student"]).status_code,403)

if __name__=="__main__":unittest.main()
