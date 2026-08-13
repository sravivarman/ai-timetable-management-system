"""Regression tests for transactional student-batch replacement."""
import os, unittest
from datetime import date
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db");os.environ.setdefault("SECRET_KEY","test-secret-that-is-at-least-thirty-two-bytes")
import app.db.models  # noqa
from fastapi import HTTPException
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.db.base import Base
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.academic_terms.models import AcademicTerm
from app.modules.sections.models import Section
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.laboratory_batches.services import service

class StudentBatchGenerationTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(self.engine);self.db=Session(self.engine)
  d=Department(department_code="TST",department_name="Test",short_name="TST");t=AcademicTerm(academic_year="2026-27",term_name="I-I",year_number=1,semester_number=1,start_date=date(2026,7,1),end_date=date(2026,11,1),is_active=True);self.db.add_all([d,t]);self.db.flush();p=Program(department_id=d.id,program_code="TST-UG",program_name="Test");self.db.add(p);self.db.flush();self.section=Section(program_id=p.id,academic_term_id=t.id,section_name="A",section_code="TST-A",student_strength=72);self.db.add(self.section);self.db.commit()
 def tearDown(self):self.db.close();self.engine.dispose()
 def active(self):return list(self.db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.section.id,StudentBatch.is_active.is_(True))))
 def test_generation_overwrite_preserves_history_and_switches_counts(self):
  first=service.batches(self.db,self.section.id,2);self.assertEqual(len(first),2)
  with self.assertRaises(HTTPException) as error:service.batches(self.db,self.section.id,2)
  self.assertEqual(error.exception.status_code,409);self.assertEqual(len(self.active()),2)
  second=service.batches(self.db,self.section.id,3,True);self.assertEqual(len(second),3);self.assertEqual(len(self.active()),3);self.assertEqual(self.db.query(StudentBatch).filter_by(section_id=self.section.id,is_active=False).count(),2)
  third=service.batches(self.db,self.section.id,1,True);self.assertEqual(len(third),1);self.assertEqual(len(self.active()),1)
  fourth=service.batches(self.db,self.section.id,2,True);self.assertEqual(len(fourth),2);self.assertEqual(len(self.active()),2);self.assertEqual(self.db.query(StudentBatch).filter_by(section_id=self.section.id,is_active=False).count(),6)
 def test_generation_supports_one_two_three_four_and_six_groups(self):
  for count in (1,2,3,4,6):
   groups=service.batches(self.db,self.section.id,count,overwrite=bool(self.active()))
   self.assertEqual(len(groups),count)
   self.assertEqual(sum(group.student_count for group in groups),72)
   self.assertLessEqual(max(group.student_count for group in groups)-min(group.student_count for group in groups),1)
   self.assertEqual([group.batch_name for group in groups],[f"A{sequence}" for sequence in range(1,count+1)])
   self.assertTrue(all(group.student_count>0 for group in groups))
 def test_large_section_custom_naming_and_group_count_validation(self):
  self.section.student_strength=600;self.db.commit()
  groups=service.batches(self.db,self.section.id,6,naming_pattern="{section_code}-GROUP-{sequence}")
  self.assertEqual([group.student_count for group in groups],[100]*6)
  self.assertEqual(groups[-1].batch_name,"TST-A-GROUP-6")
  service.batches(self.db,self.section.id,1,True,"FULL")
  self.assertEqual(self.active()[0].batch_name,"FULL")
  with self.assertRaises(HTTPException) as error:service.batches(self.db,self.section.id,601,True)
  self.assertEqual(error.exception.status_code,422)
