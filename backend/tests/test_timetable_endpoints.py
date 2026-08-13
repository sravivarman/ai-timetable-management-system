"""Isolated HTTP integration tests for timetable APIs."""
import os,unittest
from datetime import date,datetime
from uuid import UUID
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db");os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.modules.authentication.models import Permission,Role
from app.modules.academic_terms.models import AcademicTerm
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.models import Timetable,TimetableVersion
from tests.facilities_test_support import create_facilities_test_context
class TimetableEndpointTests(unittest.TestCase):
 def setUp(self):
  self.ctx=create_facilities_test_context();db=self.ctx.session_factory()
  try:
   p=[Permission(resource="timetables",action=a)for a in ("read","manage")];db.add_all(p);db.add_all([Role(name="Dean"),Role(name="Principal")]);db.flush();roles={r.name:r for r in db.scalars(select(Role)).all()};roles["Administrator"].permissions.extend(p);roles["Timetable Coordinator"].permissions.extend(p);[r.permissions.append(p[0])for r in (roles["HOD"],roles["Dean"],roles["Principal"])]
   self.term=AcademicTerm(academic_year="2026-27",term_name="I-I",year_number=1,semester_number=1,start_date=date(2026,7,1),end_date=date(2026,11,1),is_active=True);inactive=AcademicTerm(academic_year="2027-28",term_name="I-I",year_number=1,semester_number=1,start_date=date(2027,7,1),end_date=date(2027,11,1),is_active=False);db.add_all([self.term,inactive]);db.flush();self.inactive=inactive;self.passed=ValidationRun(academic_term_id=self.term.id,scope_type="COLLEGE",status="PASSED",total_checks=1,passed_checks=1,failed_checks=0,warning_checks=0,created_by=next(iter(roles["Administrator"].users)).id);self.warning=ValidationRun(academic_term_id=self.term.id,scope_type="COLLEGE",status="WARNING",total_checks=1,passed_checks=0,failed_checks=0,warning_checks=1,created_by=self.passed.created_by);self.failed=ValidationRun(academic_term_id=self.term.id,scope_type="COLLEGE",status="FAILED",total_checks=1,passed_checks=0,failed_checks=1,warning_checks=0,created_by=self.passed.created_by);db.add_all([self.passed,self.warning,self.failed]);db.commit()
  finally:db.close()
  self.client=TestClient(app)
 def tearDown(self):self.client.close();self.ctx.close()
 def payload(self):return {"academic_term_id":str(self.term.id),"scope_type":"COLLEGE","name":"Test Timetable"}
 def test_authorization_crud_and_versions(self):
  r=self.client.post("/api/v1/timetables",json=self.payload(),headers=self.ctx.headers["administrator"]);self.assertEqual(r.status_code,201,r.text);tid=r.json()["id"]
  self.assertEqual(self.client.post("/api/v1/timetables",json=self.payload()|{"name":"Coordinator"},headers=self.ctx.headers["coordinator"]).status_code,201)
  for role in ("hod",):self.assertEqual(self.client.post("/api/v1/timetables",json=self.payload(),headers=self.ctx.headers[role]).status_code,403)
  for role in ("hod",):self.assertEqual(self.client.get(f"/api/v1/timetables/{tid}",headers=self.ctx.headers[role]).status_code,200)
  self.assertEqual(self.client.get(f"/api/v1/timetables?academic_term_id={self.term.id}&scope_type=COLLEGE",headers=self.ctx.headers["administrator"]).status_code,200);self.assertEqual(self.client.put(f"/api/v1/timetables/{tid}",json={"name":"Updated"},headers=self.ctx.headers["administrator"]).status_code,200);self.assertEqual(self.client.get("/api/v1/timetables/00000000-0000-0000-0000-000000000000",headers=self.ctx.headers["administrator"]).status_code,404);self.assertEqual(self.client.post("/api/v1/timetables",json=self.payload()|{"academic_term_id":str(self.inactive.id)},headers=self.ctx.headers["administrator"]).status_code,422);self.assertEqual(self.client.post("/api/v1/timetables",json=self.payload()|{"department_id":str(self.ctx.active_department.id)},headers=self.ctx.headers["administrator"]).status_code,422)
  v={"validation_run_id":str(self.passed.id),"source_type":"GENERATED"};one=self.client.post(f"/api/v1/timetables/{tid}/versions",json=v,headers=self.ctx.headers["administrator"]);self.assertEqual(one.status_code,201,one.text);two=self.client.post(f"/api/v1/timetables/{tid}/versions",json=v,headers=self.ctx.headers["administrator"]);self.assertEqual(two.status_code,201,two.text);self.assertEqual((one.json()["version_number"],two.json()["version_number"]),(1,2));self.assertFalse(self.client.get(f"/api/v1/timetable-versions/{one.json()['id']}",headers=self.ctx.headers["administrator"]).json()["is_active"]);self.assertEqual(self.client.post(f"/api/v1/timetables/{tid}/versions",json={"validation_run_id":str(self.failed.id)},headers=self.ctx.headers["administrator"]).status_code,422);self.assertEqual(self.client.get(f"/api/v1/timetables/{tid}/versions?is_active=true",headers=self.ctx.headers["administrator"]).json()["total"],1);self.assertEqual(self.client.get(f"/api/v1/timetable-versions/{two.json()['id']}",headers=self.ctx.headers["administrator"]).status_code,200)
 def test_create_update_and_version_response_timestamps(self):
  created=self.client.post("/api/v1/timetables",json=self.payload(),headers=self.ctx.headers["administrator"])
  self.assertEqual(created.status_code,201,created.text)
  body=created.json();self.assertIsNotNone(body["created_at"]);self.assertIsNotNone(body["updated_at"])
  original_updated=datetime.fromisoformat(body["updated_at"])
  updated=self.client.put(f"/api/v1/timetables/{body['id']}",json={"name":"Timestamp Updated"},headers=self.ctx.headers["administrator"])
  self.assertEqual(updated.status_code,200,updated.text);self.assertGreater(datetime.fromisoformat(updated.json()["updated_at"]),original_updated)
  version=self.client.post(f"/api/v1/timetables/{body['id']}/versions",json={"validation_run_id":str(self.passed.id),"source_type":"GENERATED"},headers=self.ctx.headers["administrator"])
  self.assertEqual(version.status_code,201,version.text);self.assertIsNotNone(version.json()["created_at"]);self.assertIsNotNone(version.json()["updated_at"])
 def test_version_validation_status_eligibility(self):
  timetable=self.client.post("/api/v1/timetables",json=self.payload(),headers=self.ctx.headers["administrator"])
  self.assertEqual(timetable.status_code,201,timetable.text);url=f"/api/v1/timetables/{timetable.json()['id']}/versions"
  passed=self.client.post(url,json={"validation_run_id":str(self.passed.id)},headers=self.ctx.headers["administrator"])
  warning=self.client.post(url,json={"validation_run_id":str(self.warning.id)},headers=self.ctx.headers["administrator"])
  failed=self.client.post(url,json={"validation_run_id":str(self.failed.id)},headers=self.ctx.headers["administrator"])
  self.assertEqual(passed.status_code,201,passed.text);self.assertEqual(warning.status_code,201,warning.text);self.assertEqual(failed.status_code,422,failed.text);self.assertIn("PASSED or WARNING",failed.json()["detail"])
