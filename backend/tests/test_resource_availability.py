import os,unittest
from uuid import UUID
from datetime import date
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db");os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission,Role
from app.modules.facilities.models import Classroom,Laboratory
from app.modules.faculty.models import Faculty
from app.modules.resource_availability.models import ResourceAvailabilitySlot
from app.modules.resource_availability.service import availability_service
from app.modules.schedule_configuration.models import WorkingDay
from tests.facilities_test_support import create_facilities_test_context

class ResourceAvailabilityTests(unittest.TestCase):
 def setUp(self):
  self.ctx=create_facilities_test_context();db=self.ctx.session_factory()
  permissions=[]
  for resource,action in (("laboratory_blocks","read"),("laboratory_blocks","manage"),("faculty_availability","read"),("faculty_availability","manage")):
   permission=Permission(resource=resource,action=action);db.add(permission);permissions.append(permission)
  db.flush();roles={role.name:role for role in db.scalars(select(Role))};roles["Administrator"].permissions.extend(permissions)
  self.term=AcademicTerm(academic_year="2026-27",term_name="I-I",year_number=1,semester_number=1,start_date=date(2026,7,1),end_date=date(2026,11,1),is_active=True)
  self.day=WorkingDay(day_name="Monday",sequence_number=1);self.room=Classroom(room_number="G101",owning_department_id=self.ctx.active_department.id);self.lab=Laboratory(laboratory_code="GEN-LAB",laboratory_name="Generic Lab",room_number="G102",owning_department_id=self.ctx.active_department.id);self.faculty=Faculty(faculty_code="VCE900",full_name="Generic Faculty",department_id=self.ctx.active_department.id,designation="Professor",institutional_email="generic@vce.ac.in",maximum_weekly_workload=20)
  db.add_all([self.term,self.day,self.room,self.lab,self.faculty]);db.commit();db.close();self.client=TestClient(app);self.headers=self.ctx.headers["administrator"]
 def tearDown(self):self.client.close();self.ctx.close()
 def test_truth_table_is_shared_by_classroom_laboratory_and_faculty(self):
  for kind,resource in (("CLASSROOM",self.room),("LABORATORY",self.lab),("FACULTY",self.faculty)):
   mode=self.client.put(f"/api/v1/resource-availability/{kind}/{resource.id}/{self.term.id}",json={"availability_mode":"ONLY_SELECTED"},headers=self.headers);self.assertEqual(mode.status_code,200,mode.text)
   slot=self.client.post("/api/v1/resource-availability/slots",json={"resource_type":kind,"resource_id":str(resource.id),"academic_term_id":str(self.term.id),"working_day_id":str(self.day.id),"period_number":3,"availability_type":"ALLOWED"},headers=self.headers);self.assertEqual(slot.status_code,201,slot.text)
   db=self.ctx.session_factory();self.assertTrue(availability_service.is_available(db,kind,resource.id,self.term.id,self.day.id,3));self.assertFalse(availability_service.is_available(db,kind,resource.id,self.term.id,self.day.id,2));db.close()
  page=self.client.get(f"/api/v1/resource-availability/slots?resource_type=CLASSROOM&resource_id={self.room.id}",headers=self.headers);self.assertEqual(page.status_code,200);self.assertEqual(page.json()["total"],1)
 def test_legacy_lab_api_and_registry_alias_use_the_generic_store(self):
  legacy=self.client.post("/api/v1/laboratory-availability-blocks",json={"laboratory_id":str(self.lab.id),"academic_term_id":str(self.term.id),"working_day_id":str(self.day.id),"period_number":2},headers=self.headers);self.assertEqual(legacy.status_code,201,legacy.text)
  db=self.ctx.session_factory();row=db.scalar(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.id==UUID(legacy.json()["id"])));self.assertEqual(row.resource_type,"LABORATORY");db.close()
  alias=self.client.put(f"/api/v1/resource-availability/SEMINAR_HALL/{self.room.id}/{self.term.id}",json={"availability_mode":"EXCEPT_BLOCKED"},headers=self.headers);self.assertEqual(alias.status_code,200,alias.text);self.assertEqual(alias.json()["resource_type"],"CLASSROOM")

if __name__=="__main__":unittest.main()
