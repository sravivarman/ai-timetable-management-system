import os, unittest
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
from sqlalchemy import create_engine,func,select
from sqlalchemy.orm import Session,sessionmaker
import app.modules.authentication.models,app.modules.facilities.models
from app.db.base import Base
from app.modules.authentication.models import Permission,Role,User
from app.core.security import verify_password
from scripts import seed as seed_script

class FacilitiesPermissionsTests(unittest.TestCase):
 def setUp(self):self.engine=create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(self.engine);self.db=Session(self.engine)
 def tearDown(self):self.db.close();self.engine.dispose()
 def test_seed_grants_expected_facilities_permissions_without_duplicates(self):
  original=seed_script.SessionLocal;seed_script.SessionLocal=sessionmaker(bind=self.engine)
  try:seed_script.seed();seed_script.seed()
  finally:seed_script.SessionLocal=original
  expected={("classrooms","read"),("classrooms","manage"),("laboratories","read"),("laboratories","manage")}
  grants={name:{(p.resource,p.action) for p in self.db.scalar(select(Role).where(Role.name==name)).permissions} for name in ("Administrator","Timetable Coordinator","HOD")}
  self.assertTrue(expected<=grants["Administrator"]);self.assertTrue(expected<=grants["Timetable Coordinator"]);self.assertTrue({("classrooms","read"),("laboratories","read")}<=grants["HOD"]);self.assertNotIn(("classrooms","manage"),grants["HOD"]);self.assertEqual(self.db.scalar(select(func.count()).select_from(Permission).where(Permission.resource.in_(("classrooms","laboratories")))),4)
 def test_seed_grants_idempotent_timetable_entry_permissions(self):
  original=seed_script.SessionLocal;seed_script.SessionLocal=sessionmaker(bind=self.engine)
  try:seed_script.seed();seed_script.seed()
  finally:seed_script.SessionLocal=original
  grants={name:{(p.resource,p.action) for p in self.db.scalar(select(Role).where(Role.name==name)).permissions} for name in ("Administrator","Timetable Coordinator","HOD","Dean","Principal")};legacy={("timetable_entries","read"),("timetable_entries","manage")};review={("timetable_entries","move"),("timetable_entries","lock")}
  self.assertTrue(legacy|review<=grants["Administrator"]);self.assertTrue(legacy|review<=grants["Timetable Coordinator"]);self.assertTrue(review|{("timetable_entries","read")}<=grants["HOD"]);self.assertNotIn(("timetable_entries","manage"),grants["HOD"])
  for role in ("Dean","Principal"):self.assertIn(("timetable_entries","read"),grants[role]);self.assertTrue(review.isdisjoint(grants[role]));self.assertNotIn(("timetable_entries","manage"),grants[role])
  self.assertEqual(self.db.scalar(select(func.count()).select_from(Permission).where(Permission.resource=="timetable_entries")),4)
 def test_seed_grants_idempotent_timetable_solver_permissions(self):
  original=seed_script.SessionLocal;seed_script.SessionLocal=sessionmaker(bind=self.engine)
  try:seed_script.seed();seed_script.seed()
  finally:seed_script.SessionLocal=original
  grants={name:{(p.resource,p.action) for p in self.db.scalar(select(Role).where(Role.name==name)).permissions} for name in ("Administrator","Timetable Coordinator","HOD","Dean","Principal")};both={("timetable_solver","read"),("timetable_solver","run")}
  self.assertTrue(both<=grants["Administrator"]);self.assertTrue(both<=grants["Timetable Coordinator"])
  for role in ("HOD","Dean","Principal"):self.assertIn(("timetable_solver","read"),grants[role]);self.assertNotIn(("timetable_solver","run"),grants[role])
  self.assertEqual(self.db.scalar(select(func.count()).select_from(Permission).where(Permission.resource=="timetable_solver")),2)
 def test_seed_grants_idempotent_report_permission(self):
  original=seed_script.SessionLocal;original_password=seed_script.settings.report_viewer_initial_password;seed_script.SessionLocal=sessionmaker(bind=self.engine);seed_script.settings.report_viewer_initial_password="ConfiguredViewer123"
  try:
   seed_script.seed();first_hash=self.db.scalar(select(User.password_hash).where(User.username=="administrator"));seed_script.seed()
  finally:seed_script.SessionLocal=original;seed_script.settings.report_viewer_initial_password=original_password
  for name in ("Administrator","Timetable Coordinator","HOD","Dean","Principal"):
   grants={(p.resource,p.action) for p in self.db.scalar(select(Role).where(Role.name==name)).permissions}
   self.assertIn(("reports","read"),grants)
  self.assertEqual(self.db.scalar(select(func.count()).select_from(Permission).where(Permission.resource=="reports",Permission.action=="read")),1)
  viewer_role=self.db.scalar(select(Role).where(Role.name=="REPORT_VIEWER"));viewer=self.db.scalar(select(User).where(User.username=="reportviewer"));self.assertEqual({(p.resource,p.action) for p in viewer_role.permissions},{("reports","read")});self.assertEqual([role.name for role in viewer.roles],["REPORT_VIEWER"]);self.assertTrue(viewer.is_active);self.assertTrue(verify_password("ConfiguredViewer123",viewer.password_hash))
  administrator=self.db.scalar(select(User).where(User.username=="administrator"));self.assertEqual(administrator.email,"admin@vce.ac.in");self.assertEqual(administrator.password_hash,first_hash)
