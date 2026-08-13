"""HTTP authorization regression for faculty allocation routes."""

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.faculty.models import Faculty
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from tests.facilities_test_support import create_facilities_test_context


class FacultyAllocationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.context = create_facilities_test_context(); db = self.context.session_factory()
        try:
            term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True); db.add(term); db.flush()
            program = Program(department_id=self.context.active_department.id, program_code="BTECH-TST", program_name="B.Tech Test"); db.add(program); db.flush()
            section = Section(program_id=program.id, academic_term_id=term.id, section_name="A", section_code="TST-A", student_strength=60)
            course = Course(course_code="A9001", course_name="Theory", offering_department_id=self.context.active_department.id, course_type="THEORY", weekly_periods=4, counts_toward_workload=True)
            faculty = Faculty(faculty_code="VCE001", full_name="Test Faculty", department_id=self.context.active_department.id, designation="Assistant Professor", institutional_email="faculty.alloc@vce.ac.in", maximum_weekly_workload=20)
            db.add_all([section, course, faculty]); db.flush(); offering = CourseOffering(course_id=course.id, section_id=section.id, academic_term_id=term.id); db.add(offering); db.commit()
            self.offering_id, self.faculty_id = offering.id, faculty.id
        finally: db.close()
        self.client = TestClient(app)

    def tearDown(self): self.client.close(); self.context.close()

    def test_hod_manage_coordinator_read_only(self):
        payload = {"course_offering_id": str(self.offering_id), "faculty_id": str(self.faculty_id)}
        created = self.client.post("/api/v1/faculty-allocations/theory", json=payload, headers=self.context.headers["hod"])
        self.assertEqual(created.status_code, 201, created.text)
        readable = self.client.get("/api/v1/faculty-allocations/theory", headers=self.context.headers["coordinator"])
        self.assertEqual(readable.status_code, 200)
        forbidden = self.client.post("/api/v1/faculty-allocations/theory", json=payload, headers=self.context.headers["coordinator"])
        self.assertEqual(forbidden.status_code, 403)
