"""Service tests for faculty allocation eligibility and workload preview."""

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
import app.modules.academic_terms.models  # noqa: F401
import app.modules.sections.models  # noqa: F401
import app.modules.facilities.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.course_offerings.models  # noqa: F401
import app.modules.faculty.models  # noqa: F401
import app.modules.faculty_allocations.models  # noqa: F401
import app.modules.laboratory_batches.models  # noqa: F401
from app.db.base import Base
from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.departments.models import Department
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.faculty_allocations.schemas import LaboratoryAllocationCreate, LaboratorySessionRuleCreate, TheoryAllocationCreate
from app.modules.faculty_allocations.services import FacultyAllocationService
from app.modules.laboratory_batches.models import LaboratoryBatchConfiguration
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from scripts import cleanup_demo, seed_demo


class FacultyAllocationServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(self.engine); self.db = Session(self.engine)
        department = Department(department_code="CSE", department_name="Computer Science", short_name="CSE")
        term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True)
        self.db.add_all([department, term]); self.db.flush()
        program = Program(department_id=department.id, program_code="BTECH-CSE", program_name="B.Tech CSE"); self.db.add(program); self.db.flush()
        section = Section(program_id=program.id, academic_term_id=term.id, section_name="A", section_code="CSE-A", student_strength=60)
        theory = Course(course_code="A9001", course_name="Mathematics", offering_department_id=department.id, course_type="THEORY", weekly_periods=4, counts_toward_workload=True)
        lab = Course(course_code="A9201", course_name="Programming Lab", offering_department_id=department.id, course_type="LABORATORY", weekly_periods=3, counts_toward_workload=True)
        practical = Course(course_code="A9021", course_name="Community Centered Design Thinking", offering_department_id=department.id, course_type="PRACTICAL", weekly_periods=3, grouping_mode="GROUPED", default_group_count=2, session_duration=3, sessions_per_week=1, venue_requirement="CLASSROOM_ONLY", counts_toward_workload=True)
        faculty1 = Faculty(faculty_code="VCE001", full_name="Faculty One", department_id=department.id, designation="Assistant Professor", institutional_email="one@vce.ac.in", maximum_weekly_workload=20)
        faculty2 = Faculty(faculty_code="VCE002", full_name="Faculty Two", department_id=department.id, designation="Assistant Professor", institutional_email="two@vce.ac.in", maximum_weekly_workload=20)
        self.db.add_all([section, theory, lab, practical, faculty1, faculty2]); self.db.flush()
        self.theory_offering = CourseOffering(course_id=theory.id, section_id=section.id, academic_term_id=term.id)
        self.lab_offering = CourseOffering(course_id=lab.id, section_id=section.id, academic_term_id=term.id)
        self.practical_offering = CourseOffering(course_id=practical.id, section_id=section.id, academic_term_id=term.id)
        self.db.add_all([self.theory_offering, self.lab_offering, self.practical_offering]); self.db.commit()
        self.faculty1, self.faculty2, self.term, self.department, self.program = faculty1, faculty2, term, department, program; self.service = FacultyAllocationService()

    def tearDown(self): self.db.close(); self.engine.dispose()

    def test_theory_lab_rules_and_session_rules(self):
        theory = self.service.create_theory(self.db, TheoryAllocationCreate(course_offering_id=self.theory_offering.id, faculty_id=self.faculty1.id))
        with self.assertRaises(HTTPException) as split: self.service.create_theory(self.db, TheoryAllocationCreate(course_offering_id=self.theory_offering.id, faculty_id=self.faculty2.id))
        self.assertEqual(split.exception.status_code, 409)
        main = self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.lab_offering.id, faculty_id=self.faculty1.id, role_type="MAIN", minimum_sessions_per_week=1, maximum_sessions_per_week=2))
        supporting = self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.lab_offering.id, faculty_id=self.faculty2.id, role_type="SUPPORTING", required_with_main_faculty_id=self.faculty1.id))
        rule = self.service.create_rule(self.db, LaboratorySessionRuleCreate(laboratory_faculty_allocation_id=supporting.id, session_number=1, is_mandatory_for_session=True))
        self.assertTrue(rule.is_mandatory_for_session)
        with self.assertRaises(HTTPException) as last_main: self.service.soft_delete(self.db, type(main), main.id)
        self.assertEqual(last_main.exception.status_code, 422)
        with self.assertRaises(HTTPException) as wrong_type: self.service.create_theory(self.db, TheoryAllocationCreate(course_offering_id=self.lab_offering.id, faculty_id=self.faculty1.id))
        self.assertEqual(wrong_type.exception.status_code, 422)

    def test_workload_preview(self):
        self.service.create_theory(self.db, TheoryAllocationCreate(course_offering_id=self.theory_offering.id, faculty_id=self.faculty1.id))
        self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.lab_offering.id, faculty_id=self.faculty2.id, role_type="MAIN"))
        preview = {item.faculty_id: item.weekly_workload_hours for item in self.service.preview(self.db, faculty_id=None, academic_term_id=self.term.id, department_id=self.department.id)}
        self.assertEqual(preview[self.faculty1.id], 4)
        self.assertEqual(preview[self.faculty2.id], 3)

    def test_grouped_workload_counts_physical_group_occurrences_without_changing_course_periods(self):
        lab = self.db.get(Course, self.lab_offering.course_id)
        lab.weekly_periods = 3; lab.session_duration = 3; lab.sessions_per_week = 1; lab.grouping_mode = "GROUPED"; lab.default_group_count = 2
        self.db.add(LaboratoryBatchConfiguration(course_offering_id=self.lab_offering.id, section_id=self.lab_offering.section_id, number_of_groups=2))
        self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.lab_offering.id, faculty_id=self.faculty2.id, role_type="MAIN"))
        preview = {item.faculty_id: item.weekly_workload_hours for item in self.service.preview(self.db, faculty_id=None, academic_term_id=self.term.id, department_id=self.department.id)}
        self.assertEqual(lab.weekly_periods, 3)
        self.assertEqual(preview[self.faculty2.id], 6)

    def test_practical_uses_rich_activity_allocations_roles_dependencies_and_workload(self):
        self.db.add(LaboratoryBatchConfiguration(course_offering_id=self.practical_offering.id, section_id=self.practical_offering.section_id, number_of_groups=2)); self.db.commit()
        main = self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.practical_offering.id, faculty_id=self.faculty1.id, role_type="MAIN", minimum_sessions_per_week=1, maximum_sessions_per_week=1))
        supporting = self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.practical_offering.id, faculty_id=self.faculty2.id, role_type="SUPPORTING", required_with_main_faculty_id=self.faculty1.id, alternative_group_code="CCDT-SUPPORT", minimum_sessions_per_week=1, maximum_sessions_per_week=1))
        self.assertEqual((main.role_type, supporting.required_with_main_faculty_id, supporting.alternative_group_code), ("MAIN", self.faculty1.id, "CCDT-SUPPORT"))
        preview = {item.faculty_id: item.weekly_workload_hours for item in self.service.preview(self.db, faculty_id=None, academic_term_id=self.term.id, department_id=self.department.id)}
        self.assertEqual(preview[self.faculty1.id], 6)
        self.assertEqual(preview[self.faculty2.id], 6)
        with self.assertRaises(HTTPException) as activity_theory:
            self.service.create_laboratory(self.db, LaboratoryAllocationCreate(course_offering_id=self.theory_offering.id, faculty_id=self.faculty1.id, role_type="MAIN"))
        self.assertIn("laboratory or practical", activity_theory.exception.detail)
        with self.assertRaises(HTTPException):
            self.service.create_theory(self.db, TheoryAllocationCreate(course_offering_id=self.practical_offering.id, faculty_id=self.faculty1.id))

    def test_ccdt_twenty_four_section_allocations_are_all_accepted(self):
        offerings=[self.practical_offering]
        for index in range(2,25):
            section=Section(program_id=self.program.id,academic_term_id=self.term.id,section_name=str(index),section_code=f"CCDT-{index:02d}",student_strength=60)
            self.db.add(section);self.db.flush();offering=CourseOffering(course_id=self.practical_offering.course_id,section_id=section.id,academic_term_id=self.term.id);self.db.add(offering);self.db.flush();offerings.append(offering)
        self.db.commit()
        rows=[self.service.create_laboratory(self.db,LaboratoryAllocationCreate(course_offering_id=offering.id,faculty_id=self.faculty1.id,role_type="MAIN",minimum_sessions_per_week=1,maximum_sessions_per_week=1)) for offering in offerings]
        self.assertEqual(len(rows),24)
        self.assertEqual(self.db.query(LaboratoryFacultyAllocation).filter(LaboratoryFacultyAllocation.course_offering_id.in_([offering.id for offering in offerings]),LaboratoryFacultyAllocation.is_active.is_(True)).count(),24)

    def test_demo_seed_is_idempotent(self):
        original_seed, original_cleanup = seed_demo.SessionLocal, cleanup_demo.SessionLocal
        factory = sessionmaker(bind=self.engine)
        seed_demo.SessionLocal = cleanup_demo.SessionLocal = factory
        try:
            seed_demo.seed_demo(); seed_demo.seed_demo()
            self.assertEqual(self.db.query(Course).filter(Course.course_code.in_(("DEMO-THEORY-01", "DEMO-LAB-01"))).count(), 2)
            self.assertEqual(self.db.query(CourseOffering).join(Course, Course.id == CourseOffering.course_id).filter(Course.course_code.in_(("DEMO-THEORY-01", "DEMO-LAB-01"))).count(), 2)
            self.assertEqual(self.db.query(Faculty).filter(Faculty.faculty_code.in_(("VCE003", "VCE004"))).count(), 2)
        finally:
            cleanup_demo.cleanup_demo()
            seed_demo.SessionLocal, cleanup_demo.SessionLocal = original_seed, original_cleanup
