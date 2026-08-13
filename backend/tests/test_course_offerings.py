"""Tests for Course Offering behavior."""

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
import app.modules.academic_terms.models  # noqa: F401
import app.modules.sections.models  # noqa: F401
import app.modules.facilities.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.course_offerings.models  # noqa: F401
from app.db.base import Base
from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering, CourseOfferingAllowedLaboratory
from app.modules.course_offerings.laboratories import resolve_effective_laboratories
from app.modules.course_offerings.schemas import CourseOfferingBulkCreate, CourseOfferingCreate, CourseOfferingUpdate
from app.modules.course_offerings.services import CourseOfferingService
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.facilities.models import Laboratory
from scripts import seed as seed_script
from app.modules.authentication.models import Role


class CourseOfferingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.department = Department(department_code="CSE", department_name="Computer Science", short_name="CSE")
        self.program = Program(department_id=None, program_code="BTECH-CSE", program_name="B.Tech CSE")
        self.term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True)
        self.other_term = AcademicTerm(academic_year="2026-27", term_name="II-I", year_number=2, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True)
        self.db.add_all([self.department, self.term, self.other_term]); self.db.flush()
        self.program.department_id = self.department.id; self.db.add(self.program); self.db.flush()
        self.section = Section(program_id=self.program.id, academic_term_id=self.term.id, section_name="A", section_code="CSE-A", student_strength=60)
        self.theory = Course(course_code="A9001", course_name="Mathematics", offering_department_id=self.department.id, course_type="THEORY", weekly_periods=4, counts_toward_workload=True)
        self.lab = Course(course_code="A9201", course_name="Programming Lab", offering_department_id=self.department.id, course_type="LABORATORY", weekly_periods=3, counts_toward_workload=True)
        self.db.add_all([self.section, self.theory, self.lab]); self.db.commit()
        self.service = CourseOfferingService()

    def tearDown(self) -> None:
        self.db.close(); self.engine.dispose()

    def payload(self, course_id=None, **values) -> CourseOfferingCreate:
        data = {"course_id": course_id or self.theory.id, "section_id": self.section.id, "academic_term_id": self.term.id}
        data.update(values)
        return CourseOfferingCreate(**data)

    def test_validation_duplicate_common_theory_and_lifecycle(self) -> None:
        offering = self.service.create_offering(self.db, self.payload(is_common_theory=True, common_theory_group_code="CSE-COMMON"))
        self.assertTrue(offering.is_common_theory)
        with self.assertRaises(HTTPException) as duplicate:
            self.service.create_offering(self.db, self.payload())
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as lab_common:
            self.service.create_offering(self.db, self.payload(self.lab.id, is_common_theory=True, common_theory_group_code="LAB-COMMON"))
        self.assertEqual(lab_common.exception.status_code, 422)
        with self.assertRaises(HTTPException) as mismatched_term:
            self.service.create_offering(self.db, CourseOfferingCreate(course_id=self.lab.id, section_id=self.section.id, academic_term_id=self.other_term.id))
        self.assertEqual(mismatched_term.exception.status_code, 422)
        self.service.soft_delete_offering(self.db, offering.id)
        self.assertFalse(self.service.get_offering(self.db, offering.id).is_active)
        self.service.restore_offering(self.db, offering.id)
        self.assertTrue(self.service.get_offering(self.db, offering.id).is_active)

    def test_ordinary_offering_needs_no_legacy_common_theory_metadata(self) -> None:
        payload = self.payload(is_mandatory=True, weekly_periods_override=None, elective_group_name=None)
        self.assertNotIn("is_common_theory", payload.model_fields_set)
        self.assertNotIn("common_theory_group_code", payload.model_fields_set)
        offering = self.service.create_offering(self.db, payload)
        self.assertFalse(offering.is_common_theory)
        self.assertIsNone(offering.common_theory_group_code)

    def test_bulk_list_filters_and_seed_permissions(self) -> None:
        created = self.service.create_bulk(self.db, CourseOfferingBulkCreate(section_id=self.section.id, academic_term_id=self.term.id, course_ids=[self.theory.id, self.lab.id]))
        self.assertEqual(len(created), 2)
        listed = self.service.list_offerings(self.db, search="CSE-A", course_id=None, section_id=self.section.id, academic_term_id=None, department_id=self.department.id, course_type="THEORY", is_mandatory=True, is_common_theory=None, is_active=True, page=1, page_size=20)
        self.assertEqual(listed.total, 1)
        original = seed_script.SessionLocal; seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try:
            seed_script.seed(); seed_script.seed()
        finally:
            seed_script.SessionLocal = original
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CourseOffering)), 2)
        for role_name in ("Administrator", "Timetable Coordinator", "HOD"):
            role = self.db.scalar(select(Role).where(Role.name == role_name))
            self.assertTrue({("course_offerings", "read"), ("course_offerings", "manage")} <= {(p.resource, p.action) for p in role.permissions})

    def test_auto_preferred_and_fixed_laboratory_selection(self) -> None:
        laboratory = Laboratory(laboratory_code="CSE-LAB", laboratory_name="CSE Lab", room_number="L101", owning_department_id=self.department.id)
        second_section = Section(program_id=self.program.id, academic_term_id=self.term.id, section_name="B", section_code="CSE-B", student_strength=60)
        third_section = Section(program_id=self.program.id, academic_term_id=self.term.id, section_name="C", section_code="CSE-C", student_strength=60)
        self.db.add_all([laboratory, second_section, third_section]); self.db.flush()
        self.lab.default_laboratory_id = laboratory.id
        self.db.add(CourseEligibleLaboratory(course_id=self.lab.id, laboratory_id=laboratory.id)); self.db.commit()

        automatic = self.service.create_offering(self.db, self.payload(self.lab.id, laboratory_selection_mode="AUTO"))
        preferred = self.service.create_offering(self.db, CourseOfferingCreate(course_id=self.lab.id, section_id=second_section.id, academic_term_id=self.term.id, laboratory_selection_mode="PREFERRED", laboratory_override_id=laboratory.id))
        fixed = self.service.create_offering(self.db, CourseOfferingCreate(course_id=self.lab.id, section_id=third_section.id, academic_term_id=self.term.id, laboratory_selection_mode="FIXED", laboratory_override_id=laboratory.id))
        self.assertEqual((automatic.laboratory_override_id, preferred.laboratory_override_id, fixed.laboratory_selection_mode), (None, laboratory.id, "FIXED"))

        outsider = Laboratory(laboratory_code="OTHER", laboratory_name="Other", room_number="OTHER", owning_department_id=self.department.id)
        self.db.add(outsider); self.db.commit()
        with self.assertRaises(HTTPException) as invalid:
            self.service.update_offering(self.db, fixed.id, CourseOfferingUpdate(laboratory_override_id=outsider.id))
        self.assertEqual(invalid.exception.status_code, 422)

    def test_restricted_laboratory_sets_are_normalized_validated_and_replaceable(self) -> None:
        laboratories = [
            Laboratory(laboratory_code=code, laboratory_name=f"Physics {code}", room_number=code, owning_department_id=self.department.id)
            for code in ("1117", "3117", "5014")
        ]
        sections = [
            Section(program_id=self.program.id, academic_term_id=self.term.id, section_name=name, section_code=f"CSE-{name}", student_strength=60)
            for name in ("B", "C", "D")
        ]
        self.db.add_all([*laboratories, *sections]); self.db.flush()
        self.db.add_all([
            CourseEligibleLaboratory(course_id=self.lab.id, laboratory_id=laboratory.id, preference_priority=index)
            for index, laboratory in enumerate(laboratories, start=1)
        ]); self.db.commit()

        one = self.service.create_offering(self.db, self.payload(self.lab.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=[laboratories[0].id]))
        two = self.service.create_offering(self.db, CourseOfferingCreate(course_id=self.lab.id, section_id=sections[0].id, academic_term_id=self.term.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=[laboratories[1].id, laboratories[2].id]))
        three = self.service.create_offering(self.db, CourseOfferingCreate(course_id=self.lab.id, section_id=sections[1].id, academic_term_id=self.term.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=[item.id for item in laboratories]))
        self.assertEqual(one.allowed_laboratory_ids, [laboratories[0].id])
        self.assertEqual([item.id for item in resolve_effective_laboratories(self.db, self.lab, two)], [laboratories[1].id, laboratories[2].id])
        self.assertEqual(len(three.allowed_laboratory_ids), 3)
        updated = self.service.update_offering(self.db, two.id, CourseOfferingUpdate(allowed_laboratory_ids=[laboratories[2].id]))
        self.assertEqual(updated.allowed_laboratory_ids, [laboratories[2].id])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CourseOfferingAllowedLaboratory).where(CourseOfferingAllowedLaboratory.course_offering_id == two.id, CourseOfferingAllowedLaboratory.is_active.is_(True))), 1)

    def test_restricted_laboratory_validation_rejects_invalid_sets(self) -> None:
        eligible = Laboratory(laboratory_code="ELIGIBLE", laboratory_name="Eligible", room_number="E-1", owning_department_id=self.department.id)
        inactive = Laboratory(laboratory_code="INACTIVE", laboratory_name="Inactive", room_number="I-1", owning_department_id=self.department.id, is_active=False)
        other_department = Department(department_code="ECE", department_name="Electronics", short_name="ECE")
        self.db.add_all([eligible, inactive, other_department]); self.db.flush()
        nonshareable = Laboratory(laboratory_code="PRIVATE", laboratory_name="Private", room_number="P-1", owning_department_id=other_department.id, is_shareable_across_departments=False)
        self.db.add(nonshareable); self.db.flush()
        self.db.add_all([CourseEligibleLaboratory(course_id=self.lab.id, laboratory_id=item.id) for item in (eligible, inactive, nonshareable)]); self.db.commit()
        for allowed_ids in ([], [inactive.id], [nonshareable.id]):
            with self.subTest(allowed_ids=allowed_ids), self.assertRaises(HTTPException) as rejected:
                self.service.create_offering(self.db, self.payload(self.lab.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=allowed_ids))
            self.assertEqual(rejected.exception.status_code, 422)
        outsider = Laboratory(laboratory_code="OUTSIDE", laboratory_name="Outside", room_number="O-1", owning_department_id=self.department.id)
        self.db.add(outsider); self.db.commit()
        with self.assertRaises(HTTPException) as not_eligible:
            self.service.create_offering(self.db, self.payload(self.lab.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=[outsider.id]))
        self.assertEqual(not_eligible.exception.status_code, 422)
        with self.assertRaises(ValueError):
            CourseOfferingCreate(course_id=self.lab.id, section_id=self.section.id, academic_term_id=self.term.id, laboratory_selection_mode="RESTRICTED", allowed_laboratory_ids=[eligible.id, eligible.id])
