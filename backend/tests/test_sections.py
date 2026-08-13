"""Unit tests for Section behavior."""
import os
import unittest
from datetime import date
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
import app.modules.academic_terms.models  # noqa: F401
import app.modules.sections.models  # noqa: F401
from app.db.base import Base
from app.modules.academic_terms.models import AcademicTerm
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.sections.schemas import SectionBulkCreate, SectionCreate, SectionInput, SectionUpdate
from app.modules.sections.services import SectionService
from app.modules.authentication.models import Role
from scripts import seed as seed_script


class SectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(self.engine); self.db = Session(self.engine)
        self.department = Department(department_code="CSE", department_name="Computer Science", short_name="CSE")
        self.db.add(self.department); self.db.flush()
        self.program = Program(department_id=self.department.id, program_code="BTECH-CSE", program_name="B.Tech CSE")
        self.term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True, is_first_year_term=True)
        self.db.add_all([self.program, self.term]); self.db.commit(); self.service = SectionService()
    def tearDown(self): self.db.close(); self.engine.dispose()
    def test_create_code_duplicate_and_parent_activity(self):
        section = self.service.create_section(self.db, SectionCreate(program_id=self.program.id, academic_term_id=self.term.id, section_name="a", student_strength=72))
        self.assertEqual(section.section_code, "CSE-A")
        with self.assertRaises(HTTPException) as duplicate: self.service.create_section(self.db, SectionCreate(program_id=self.program.id, academic_term_id=self.term.id, section_name="A", student_strength=72))
        self.assertEqual(duplicate.exception.status_code, 409)
        self.program.is_active = False; self.db.commit()
        with self.assertRaises(HTTPException): self.service.create_section(self.db, SectionCreate(program_id=self.program.id, academic_term_id=self.term.id, section_name="B", student_strength=72))
    def test_bulk_filter_lifecycle_and_permissions(self):
        bulk = self.service.bulk_create(self.db, SectionBulkCreate(program_id=self.program.id, academic_term_id=self.term.id, sections=[SectionInput(section_name="A", student_strength=70), SectionInput(section_name="B", student_strength=71)]))
        self.assertEqual([item.section_code for item in bulk], ["CSE-A", "CSE-B"])
        results = self.service.list_sections(self.db, search="CSE-A", program_id=self.program.id, term_id=None, department_id=None, year_number=1, is_active=True, page=1, page_size=20)
        self.assertEqual(results.total, 1)
        self.service.soft_delete(self.db, bulk[0].id); self.assertFalse(self.service.get_section(self.db, bulk[0].id).is_active)
        self.service.restore(self.db, bulk[0].id); self.assertTrue(self.service.get_section(self.db, bulk[0].id).is_active)
        self.assertEqual(self.service.update_section(self.db, bulk[0].id, SectionUpdate(section_name="C")).section_code, "CSE-C")
        original = seed_script.SessionLocal; seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try: seed_script.seed(); seed_script.seed()
        finally: seed_script.SessionLocal = original
        admin = self.db.scalar(select(Role).where(Role.name == "Administrator")); coordinator = self.db.scalar(select(Role).where(Role.name == "Timetable Coordinator"))
        self.assertTrue({("sections", "read"), ("sections", "manage")} <= {(p.resource, p.action) for p in admin.permissions})
        self.assertIn(("sections", "read"), {(p.resource, p.action) for p in coordinator.permissions})

if __name__ == "__main__": unittest.main()
