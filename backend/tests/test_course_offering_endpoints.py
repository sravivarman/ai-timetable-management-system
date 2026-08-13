"""HTTP integration regression for Course Offering routes."""

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient

from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.courses.models import Course
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from tests.facilities_test_support import create_facilities_test_context


class CourseOfferingEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        db = self.context.session_factory()
        try:
            term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True)
            db.add(term); db.flush()
            program = Program(department_id=self.context.active_department.id, program_code="BTECH-TST", program_name="B.Tech Test")
            db.add(program); db.flush()
            section = Section(program_id=program.id, academic_term_id=term.id, section_name="A", section_code="TST-A", student_strength=60)
            course = Course(course_code="A9001", course_name="Test Theory", offering_department_id=self.context.active_department.id, course_type="THEORY", weekly_periods=4, counts_toward_workload=True)
            db.add_all([section, course]); db.commit()
            self.term_id, self.section_id, self.course_id = term.id, section.id, course.id
        finally:
            db.close()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close(); self.context.close()

    def test_create_bulk_list_and_authorization(self) -> None:
        payload = {"course_id": str(self.course_id), "section_id": str(self.section_id), "academic_term_id": str(self.term_id)}
        created = self.client.post("/api/v1/course-offerings", json=payload, headers=self.context.headers["administrator"])
        self.assertEqual(created.status_code, 201, created.text)
        self.assertFalse(created.json()["is_common_theory"]); self.assertIsNone(created.json()["common_theory_group_code"])
        listed = self.client.get("/api/v1/course-offerings?search=TST-A", headers=self.context.headers["hod"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        forbidden = self.client.post("/api/v1/course-offerings/bulk", json={"section_id": str(self.section_id), "academic_term_id": str(self.term_id), "course_ids": [str(self.course_id)]}, headers=self.context.headers["unauthorized"])
        self.assertEqual(forbidden.status_code, 403)
