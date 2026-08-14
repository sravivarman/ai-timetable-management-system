import os, unittest
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db"); os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session,sessionmaker
import app.db.models  # noqa: F401 - register every ForeignKey target
from app.db.base import Base
from app.modules.departments.models import Department
from app.modules.faculty.schemas import FacultyCreate,FacultyUpdate
from app.modules.faculty.services import faculty_service
from app.modules.authentication.models import Role,User
from scripts import seed as seed_script
class FacultyTests(unittest.TestCase):
 def setUp(self):
  self.e=create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(self.e);self.db=Session(self.e);self.d=Department(department_code="CSE",department_name="CSE",short_name="CSE");self.db.add(self.d);self.db.commit()
 def tearDown(self):self.db.close();self.e.dispose()
 def payload(self,**x):
  v={"faculty_code":"vce001","full_name":"Dr Ada","department_id":self.d.id,"designation":"Assistant Professor","institutional_email":"ada@vce.ac.in","maximum_weekly_workload":18};v.update(x);return FacultyCreate(**v)
 def test_rules_and_lifecycle(self):
  f=faculty_service.create(self.db,self.payload());self.assertEqual(f.faculty_code,"VCE001")
  self.assertIsNone(f.user_id)
  with self.assertRaises(HTTPException): faculty_service.create(self.db,self.payload(institutional_email="other@vce.ac.in"))
  with self.assertRaises(ValidationError): self.payload(minimum_weekly_workload=20,maximum_weekly_workload=10)
  faculty_service.delete(self.db,f.id);self.assertFalse(faculty_service.get(self.db,f.id).is_active);faculty_service.restore(self.db,f.id);self.assertTrue(faculty_service.get(self.db,f.id).is_active)
  self.assertEqual(faculty_service.update(self.db,f.id,FacultyUpdate(faculty_code="vce002")).faculty_code,"VCE002")
 def test_optional_user_link_remains_supported(self):
  user=User(username="faculty-linked",email="faculty.link@vce.ac.in",full_name="Linked Faculty",password_hash="not-used");self.db.add(user);self.db.commit()
  faculty=faculty_service.create(self.db,self.payload(user_id=user.id));self.assertEqual(faculty.user_id,user.id)
 def test_seed_permissions(self):
  original=seed_script.SessionLocal;seed_script.SessionLocal=sessionmaker(bind=self.e)
  try:seed_script.seed();seed_script.seed()
  finally:seed_script.SessionLocal=original
  admin=self.db.scalar(select(Role).where(Role.name=="Administrator"));ttc=self.db.scalar(select(Role).where(Role.name=="Timetable Coordinator"));hod=self.db.scalar(select(Role).where(Role.name=="HOD"))
  self.assertTrue({("faculty","read"),("faculty","manage")} <= {(p.resource,p.action) for p in admin.permissions});self.assertIn(("faculty","read"),{(p.resource,p.action) for p in ttc.permissions});self.assertIn(("faculty","read"),{(p.resource,p.action) for p in hod.permissions})
