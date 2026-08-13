"""HTTP integration coverage for timetable-entry persistence and conflicts."""
import os
import unittest
from datetime import date
from uuid import UUID

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")

from sqlalchemy import select
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission,Role
from app.modules.course_offerings.models import CourseOffering
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.faculty_scheduling.models import FacultyAvailability
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.timetables.models import TimetableEntry
from app.modules.timetables.entry_service import entry_service
from app.modules.timetables.entry_schemas import TimetableEntryCreate
from tests import test_solver_input_builder as solver_support

class TimetableEntryEndpointTests(unittest.TestCase):
 def setUp(self):
  self.fixture=solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready");self.fixture.setUp();self.ctx=self.fixture.ctx;self.client=self.fixture.client
  db=self.ctx.session_factory()
  try:
   permissions=[Permission(resource="timetable_entries",action="read"),Permission(resource="timetable_entries",action="manage")];db.add_all(permissions);db.flush();roles={role.name:role for role in db.scalars(select(Role)).all()};roles["Administrator"].permissions.extend(permissions);roles["Timetable Coordinator"].permissions.extend(permissions);roles["HOD"].permissions.append(permissions[0]);db.commit()
   self.lab_allocation=db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id==self.fixture.lab_offering.id));self.batch=db.scalar(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id,StudentBatch.sequence_number==1))
  finally:db.close()
  self.version_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/entries"
 def tearDown(self):self.fixture.tearDown()
 def theory_payload(self,period=1,**changes):
  payload={"course_offering_id":str(self.fixture.theory_offering.id),"section_id":str(self.fixture.section.id),"faculty_id":str(self.fixture.faculty.id),"classroom_id":str(self.fixture.classroom.id),"working_day_id":str(self.fixture.working_day.id),"period_number":period,"session_length":1,"entry_type":"THEORY","is_manual":True};payload.update(changes);return payload
 def lab_payload(self,period=5,**changes):
  payload={"course_offering_id":str(self.fixture.lab_offering.id),"section_id":str(self.fixture.section.id),"laboratory_faculty_allocation_id":str(self.lab_allocation.id),"laboratory_id":str(self.fixture.laboratory.id),"student_batch_id":str(self.batch.id),"working_day_id":str(self.fixture.working_day.id),"period_number":period,"session_length":2,"entry_type":"LABORATORY","is_manual":True};payload.update(changes);return payload
 def post(self,payload,role="administrator"):return self.client.post(self.version_url,json=payload,headers=self.ctx.headers[role])

 def test_theory_laboratory_create_and_shape_validation(self):
  theory=self.post(self.theory_payload());self.assertEqual(theory.status_code,201,theory.text)
  laboratory=self.post(self.lab_payload());self.assertEqual(laboratory.status_code,201,laboratory.text)
  self.assertEqual(self.post(self.theory_payload(period_number=8)).status_code,422)
  self.assertEqual(self.post(self.lab_payload(period=7)).status_code,422)
  mismatch=self.post(self.theory_payload(period=2,section_id=str(self.fixture.other_section.id)));self.assertEqual(mismatch.status_code,422,mismatch.text)
  db=self.ctx.session_factory()
  try:
   other_term=AcademicTerm(academic_year="2027-28",term_name="I-I",year_number=1,semester_number=1,start_date=date(2027,7,1),end_date=date(2027,11,1),is_active=True);db.add(other_term);db.flush();offering=CourseOffering(course_id=self.fixture.theory_course.id,section_id=self.fixture.section.id,academic_term_id=other_term.id);db.add(offering);db.commit();offering_id=offering.id
  finally:db.close()
  term_mismatch=self.post(self.theory_payload(period=3,course_offering_id=str(offering_id)));self.assertEqual(term_mismatch.status_code,422,term_mismatch.text);self.assertIn("academic term",term_mismatch.json()["detail"])

 def test_overlap_reports_section_faculty_classroom_laboratory_and_batch(self):
  self.assertEqual(self.post(self.theory_payload()).status_code,201)
  theory_conflict=self.post(self.theory_payload());self.assertEqual(theory_conflict.status_code,409);self.assertTrue(all(name in theory_conflict.json()["detail"] for name in ("section","faculty","classroom")))
  self.assertEqual(self.post(self.lab_payload()).status_code,201)
  lab_conflict=self.post(self.lab_payload());self.assertEqual(lab_conflict.status_code,409);self.assertTrue(all(name in lab_conflict.json()["detail"] for name in ("laboratory","student_batch")))

 def test_hard_constraints_lunch_short_break_block_and_unavailability(self):
  lunch=self.post(self.lab_payload(period=3));self.assertEqual(lunch.status_code,422,lunch.text);self.assertIn("lunch",lunch.json()["detail"])
  blocked=self.post(self.lab_payload(period=6));self.assertEqual(blocked.status_code,409,blocked.text);self.assertIn("blocked",blocked.json()["detail"])
  short_break=self.post(self.lab_payload(period=5));self.assertEqual(short_break.status_code,201,short_break.text)
  db=self.ctx.session_factory()
  try:
   availability=db.scalar(select(FacultyAvailability).where(FacultyAvailability.id==self.fixture.availability.id));availability.availability_type="unavailable";db.commit()
  finally:db.close()
  unavailable=self.post(self.theory_payload(period=1));self.assertEqual(unavailable.status_code,409,unavailable.text);self.assertIn("unavailable",unavailable.json()["detail"])

 def test_lifecycle_filters_and_permissions(self):
  self.assertEqual(self.post(self.theory_payload(),"hod").status_code,403);self.assertEqual(self.post(self.theory_payload(),"unauthorized").status_code,403)
  locked=self.post(self.theory_payload(is_locked=True),"coordinator");self.assertEqual(locked.status_code,201,locked.text);entry_id=locked.json()["id"]
  self.assertEqual(self.client.get(f"/api/v1/timetable-entries/{entry_id}",headers=self.ctx.headers["hod"]).status_code,200)
  listing=self.client.get(self.version_url+"?entry_type=THEORY&is_manual=true&is_locked=true&page=1&page_size=1",headers=self.ctx.headers["hod"]);self.assertEqual(listing.status_code,200,listing.text);self.assertEqual((listing.json()["total"],listing.json()["page_size"]),(1,1))
  self.assertEqual(self.client.put(f"/api/v1/timetable-entries/{entry_id}",json={"period_number":2},headers=self.ctx.headers["administrator"]).status_code,409);self.assertEqual(self.client.delete(f"/api/v1/timetable-entries/{entry_id}",headers=self.ctx.headers["administrator"]).status_code,409)
  open_entry=self.post(self.theory_payload(period=2));self.assertEqual(open_entry.status_code,201,open_entry.text);open_id=open_entry.json()["id"]
  updated=self.client.put(f"/api/v1/timetable-entries/{open_id}",json={"period_number":3},headers=self.ctx.headers["administrator"]);self.assertEqual(updated.status_code,200,updated.text);self.assertEqual(updated.json()["period_number"],3);self.assertEqual(self.client.delete(f"/api/v1/timetable-entries/{open_id}",headers=self.ctx.headers["administrator"]).status_code,204)

 def test_locked_entries_are_deterministic_solver_inputs_and_change_hash(self):
  entry=self.post(self.theory_payload(is_locked=True));self.assertEqual(entry.status_code,201,entry.text);entry_id=UUID(entry.json()["id"])
  build_url=f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input"
  first=self.client.post(build_url,headers=self.ctx.headers["administrator"]);same=self.client.post(build_url,headers=self.ctx.headers["administrator"]);self.assertEqual(first.status_code,201,first.text);self.assertEqual(first.json()["id"],same.json()["id"]);self.assertEqual(first.json()["input_hash"],same.json()["input_hash"]);self.assertEqual(first.json()["snapshot_json"]["locked_entries"][0]["id"],str(entry_id))
  db=self.ctx.session_factory()
  try:
   persisted=db.get(TimetableEntry,entry_id);persisted.period_number=2;db.commit()
  finally:db.close()
  changed=self.client.post(build_url,headers=self.ctx.headers["administrator"]);self.assertEqual(changed.status_code,201,changed.text);self.assertNotEqual(first.json()["input_hash"],changed.json()["input_hash"])

 def test_generated_replacement_preserves_locked_entries(self):
  locked=self.post(self.theory_payload(period=1,is_manual=False,is_locked=True));generated=self.post(self.theory_payload(period=2,is_manual=False));self.assertEqual(locked.status_code,201,locked.text);self.assertEqual(generated.status_code,201,generated.text)
  db=self.ctx.session_factory()
  try:
   replacement=TimetableEntryCreate(**self.theory_payload(period=3,is_manual=False));entry_service.replace_generated(db,self.fixture.version.id,[replacement])
   rows=list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id==self.fixture.version.id)))
   self.assertEqual(len(rows),2);self.assertIn(locked.json()["id"],{str(row.id) for row in rows});self.assertNotIn(generated.json()["id"],{str(row.id) for row in rows});self.assertEqual({row.period_number for row in rows},{1,3});self.assertTrue(next(row for row in rows if str(row.id)==locked.json()["id"]).is_locked)
  finally:db.close()

if __name__=="__main__":unittest.main()
