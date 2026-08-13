"""Dedicated HTTP tests for facilities constraint endpoints."""
import os, unittest
from datetime import date
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db");os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.modules.authentication.models import Permission,Role
from app.modules.academic_terms.models import AcademicTerm
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.schedule_configuration.models import WorkingDay
from tests.facilities_test_support import create_facilities_test_context

class FacilitiesConstraintsEndpointTests(unittest.TestCase):
 def setUp(self):
  self.ctx=create_facilities_test_context();db=self.ctx.session_factory()
  try:
   permissions=[]
   for r,a in (("section_classrooms","read"),("section_classrooms","manage"),("laboratory_blocks","read"),("laboratory_blocks","manage")):
    p=Permission(resource=r,action=a);db.add(p);permissions.append(p)
   db.flush();roles={x.name:x for x in db.scalars(select(Role)).all()};roles["Administrator"].permissions.extend(permissions);roles["Timetable Coordinator"].permissions.extend(permissions);roles["HOD"].permissions.extend([permissions[0],permissions[2],permissions[3]])
   term=AcademicTerm(academic_year="2026-27",term_name="I-I",year_number=1,semester_number=1,start_date=date(2026,7,1),end_date=date(2026,11,1),is_active=True);db.add(term);db.flush();program=Program(department_id=self.ctx.active_department.id,program_code="TST-C",program_name="Test");db.add(program);db.flush();section=Section(program_id=program.id,academic_term_id=term.id,section_name="A",section_code="TST-A",student_strength=72);room=Classroom(room_number="R101",owning_department_id=self.ctx.active_department.id);lab=Laboratory(laboratory_code="TST-L",laboratory_name="Test Lab",room_number="L101",owning_department_id=self.ctx.active_department.id);day=WorkingDay(day_name="Monday",sequence_number=1);db.add_all([section,room,lab,day]);db.commit();self.term,self.section,self.room,self.lab,self.day=term,section,room,lab,day
  finally:db.close()
  self.client=TestClient(app)
 def tearDown(self):self.client.close();self.ctx.close()
 def test_section_assignment_lifecycle_validation_and_permissions(self):
  p={"section_id":str(self.section.id),"classroom_id":str(self.room.id),"academic_term_id":str(self.term.id),"is_primary":True};r=self.client.post("/api/v1/section-classroom-assignments",json=p,headers=self.ctx.headers["administrator"]);self.assertEqual(r.status_code,201,r.text);id=r.json()["id"]
  self.assertEqual(self.client.get("/api/v1/section-classroom-assignments?section_id="+str(self.section.id),headers=self.ctx.headers["hod"]).json()["total"],1);self.assertEqual(self.client.get(f"/api/v1/section-classroom-assignments/{id}",headers=self.ctx.headers["hod"]).status_code,200);self.assertEqual(self.client.put(f"/api/v1/section-classroom-assignments/{id}",json={"is_primary":False},headers=self.ctx.headers["coordinator"]).status_code,200);self.assertEqual(self.client.put(f"/api/v1/section-classroom-assignments/{id}",json={"is_primary":True},headers=self.ctx.headers["hod"]).status_code,403)
  self.assertEqual(self.client.post("/api/v1/section-classroom-assignments",json=p,headers=self.ctx.headers["administrator"]).status_code,409);self.assertEqual(self.client.delete(f"/api/v1/section-classroom-assignments/{id}",headers=self.ctx.headers["administrator"]).status_code,204);self.assertEqual(self.client.post(f"/api/v1/section-classroom-assignments/{id}/restore",headers=self.ctx.headers["coordinator"]).status_code,200)
 def test_laboratory_blocks_lifecycle_validation_filters_and_permissions(self):
  p={"laboratory_id":str(self.lab.id),"academic_term_id":str(self.term.id),"working_day_id":str(self.day.id),"period_number":1};r=self.client.post("/api/v1/laboratory-availability-blocks",json=p,headers=self.ctx.headers["hod"]);self.assertEqual(r.status_code,201,r.text);id=r.json()["id"]
  self.assertEqual(self.client.get("/api/v1/laboratory-availability-blocks?period_number=1",headers=self.ctx.headers["coordinator"]).json()["total"],1);self.assertEqual(self.client.get(f"/api/v1/laboratory-availability-blocks/{id}",headers=self.ctx.headers["administrator"]).status_code,200);self.assertEqual(self.client.put(f"/api/v1/laboratory-availability-blocks/{id}",json={"reason":"Maintenance"},headers=self.ctx.headers["coordinator"]).status_code,200);self.assertEqual(self.client.post("/api/v1/laboratory-availability-blocks",json=p,headers=self.ctx.headers["administrator"]).status_code,409);self.assertEqual(self.client.post("/api/v1/laboratory-availability-blocks",json=p|{"period_number":8},headers=self.ctx.headers["administrator"]).status_code,422);self.assertEqual(self.client.delete(f"/api/v1/laboratory-availability-blocks/{id}",headers=self.ctx.headers["hod"]).status_code,204);self.assertEqual(self.client.post(f"/api/v1/laboratory-availability-blocks/{id}/restore",headers=self.ctx.headers["administrator"]).status_code,200)
  db=self.ctx.session_factory()
  try:
   lab=db.get(Laboratory,self.lab.id);self.assertEqual(lab.availability_mode,"EXCEPT_BLOCKED");self.assertFalse(lab.is_available_all_periods)
  finally:db.close()

 def test_selected_period_rows_and_mode_conflicts(self):
  db=self.ctx.session_factory()
  try:
   lab=db.get(Laboratory,self.lab.id);lab.availability_mode="ONLY_SELECTED";lab.is_available_all_periods=False;db.commit()
  finally:db.close()
  payload={"laboratory_id":str(self.lab.id),"academic_term_id":str(self.term.id),"working_day_id":str(self.day.id),"period_number":5,"availability_type":"ALLOWED"}
  created=self.client.post("/api/v1/laboratory-availability-blocks",json=payload,headers=self.ctx.headers["administrator"]);self.assertEqual(created.status_code,201,created.text);self.assertEqual(created.json()["availability_type"],"ALLOWED")
  mismatch=self.client.post("/api/v1/laboratory-availability-blocks",json=payload|{"period_number":6,"availability_type":"BLOCKED"},headers=self.ctx.headers["administrator"]);self.assertEqual(mismatch.status_code,422,mismatch.text);self.assertIn("LAB_AVAILABILITY_CONFLICT",mismatch.text)

 def test_slot_recreation_preserves_soft_deleted_history(self):
  payload={"laboratory_id":str(self.lab.id),"academic_term_id":str(self.term.id),"working_day_id":str(self.day.id),"period_number":2}
  first=self.client.post("/api/v1/laboratory-availability-blocks",json=payload,headers=self.ctx.headers["administrator"]);self.assertEqual(first.status_code,201,first.text)
  self.assertEqual(self.client.delete(f"/api/v1/laboratory-availability-blocks/{first.json()['id']}",headers=self.ctx.headers["administrator"]).status_code,204)
  second=self.client.post("/api/v1/laboratory-availability-blocks",json=payload,headers=self.ctx.headers["administrator"]);self.assertEqual(second.status_code,201,second.text)
  inactive=self.client.get("/api/v1/laboratory-availability-blocks?is_active=false",headers=self.ctx.headers["administrator"]);self.assertEqual(inactive.json()["total"],1)
  restore=self.client.post(f"/api/v1/laboratory-availability-blocks/{first.json()['id']}/restore",headers=self.ctx.headers["administrator"]);self.assertEqual(restore.status_code,409,restore.text)
