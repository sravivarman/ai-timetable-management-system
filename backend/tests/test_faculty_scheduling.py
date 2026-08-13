import os,unittest
from datetime import date
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db");os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import app.modules.authentication.models,app.modules.departments.models,app.modules.faculty.models,app.modules.academic_terms.models,app.modules.faculty_scheduling.models
from app.db.base import Base
from app.modules.departments.models import Department
from app.modules.faculty.models import Faculty
from app.modules.academic_terms.models import AcademicTerm
from app.modules.faculty_scheduling.schemas import AvailabilityCreate,PolicyCreate
from app.modules.faculty_scheduling.services import scheduling_service
class SchedulingTests(unittest.TestCase):
 def setUp(self):
  self.e=create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(self.e);self.db=Session(self.e);d=Department(department_code="CSE",department_name="CSE",short_name="CSE");self.db.add(d);self.db.flush();self.f=Faculty(faculty_code="VCE001",full_name="Ada",department_id=d.id,designation="Assistant Professor",institutional_email="a@vce.ac.in",maximum_weekly_workload=18);self.t=AcademicTerm(academic_year="2026-27",term_name="I-I",year_number=1,semester_number=1,start_date=date(2026,7,1),end_date=date(2026,11,1),is_active=True);self.db.add_all([self.f,self.t]);self.db.commit()
 def tearDown(self):self.db.close();self.e.dispose()
 def test_availability_and_policy(self):
  a=scheduling_service.create_availability(self.db,AvailabilityCreate(faculty_id=self.f.id,academic_term_id=self.t.id,day_of_week="Monday",period_number=1,availability_type="unavailable"));self.assertEqual(a.availability_type,"unavailable")
  with self.assertRaises(HTTPException):scheduling_service.create_availability(self.db,AvailabilityCreate(faculty_id=self.f.id,academic_term_id=self.t.id,day_of_week="Monday",period_number=1,availability_type="avoid"))
  p=scheduling_service.create_policy(self.db,PolicyCreate(faculty_id=self.f.id,academic_term_id=self.t.id,maximum_periods_per_day=5,preferred_working_days=["Monday","Tuesday"]));self.assertEqual(p.maximum_periods_per_day,5)
