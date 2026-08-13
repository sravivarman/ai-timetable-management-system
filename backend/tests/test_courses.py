"""Tests for the Course master feature."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.facilities.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
from app.db.base import Base
from app.modules.authentication.models import Role
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.courses.schemas import CourseCreate, CourseUpdate
from app.modules.courses.services import CourseService
from app.modules.departments.models import Department
from app.modules.facilities.models import Laboratory
from scripts import seed as seed_script


class CourseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.active_department = Department(department_code="CSE", department_name="Computer Science", short_name="CSE")
        self.inactive_department = Department(department_code="ECE", department_name="Electronics", short_name="ECE", is_active=False)
        self.db.add_all([self.active_department, self.inactive_department])
        self.db.commit()
        self.laboratory = Laboratory(laboratory_code="CSELAB", laboratory_name="CSE Laboratory", room_number="L101", owning_department_id=self.active_department.id)
        self.db.add(self.laboratory)
        self.db.commit()
        self.service = CourseService()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def theory_payload(self, code: str = "A9001") -> CourseCreate:
        return CourseCreate(course_code=code, course_name="Engineering Mathematics", offering_department_id=self.active_department.id, course_type="THEORY", weekly_periods=4)

    def test_type_rules_defaults_and_duplicates(self) -> None:
        theory = self.service.create_course(self.db, self.theory_payload(" a9001 "))
        self.assertEqual(theory.course_code, "A9001")
        self.assertTrue(theory.counts_toward_workload)

        project = self.service.create_course(self.db, CourseCreate(course_code="A9002", course_name="Mini Project", offering_department_id=self.active_department.id, course_type="MINI_PROJECT", weekly_periods=2))
        self.assertFalse(project.counts_toward_workload)

        laboratory = self.service.create_course(self.db, CourseCreate(course_code="A9201", course_name="Programming Lab", offering_department_id=self.active_department.id, course_type="LABORATORY", weekly_periods=3, lab_session_duration=3, lab_sessions_per_week=1, default_lab_group_count=2, default_laboratory_id=self.laboratory.id))
        self.assertTrue(laboratory.counts_toward_workload)

        with self.assertRaises(HTTPException) as duplicate:
            self.service.create_course(self.db, self.theory_payload("A9001"))
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as invalid_lab:
            self.service.create_course(self.db, CourseCreate(course_code="A9202", course_name="Invalid Lab", offering_department_id=self.active_department.id, course_type="LABORATORY", weekly_periods=3))
        self.assertEqual(invalid_lab.exception.status_code, 422)
        with self.assertRaises(HTTPException) as inactive:
            self.service.create_course(self.db, CourseCreate(course_code="A9003", course_name="Inactive Department", offering_department_id=self.inactive_department.id, course_type="THEORY", weekly_periods=3))
        self.assertEqual(inactive.exception.status_code, 422)

    def test_list_update_soft_delete_and_restore(self) -> None:
        first = self.service.create_course(self.db, self.theory_payload())
        self.service.create_course(self.db, CourseCreate(course_code="A9205", course_name="Data Structures", offering_department_id=self.active_department.id, course_type="CDC", weekly_periods=4, elective_type="PROFESSIONAL_ELECTIVE"))
        found = self.service.list_courses(self.db, search="data structures", offering_department_id=self.active_department.id, course_type=None, elective_type=None, counts_toward_workload=None, is_active=True, page=1, page_size=1)
        self.assertEqual(found.total, 1)
        self.assertEqual(found.items[0].course_code, "A9205")
        updated = self.service.update_course(self.db, first.id, CourseUpdate(course_name="Updated Mathematics"))
        self.assertEqual(updated.course_name, "Updated Mathematics")
        self.service.soft_delete_course(self.db, first.id)
        self.assertEqual(self.service.list_courses(self.db, search=None, offering_department_id=None, course_type=None, elective_type=None, counts_toward_workload=None, is_active=True, page=1, page_size=20).total, 1)
        self.assertEqual(self.service.list_courses(self.db, search=None, offering_department_id=None, course_type=None, elective_type=None, counts_toward_workload=None, is_active=False, page=1, page_size=20).total, 1)
        self.service.restore_course(self.db, first.id)
        self.assertTrue(self.service.get_course(self.db, first.id).is_active)

    def test_practical_grouping_session_and_venue_are_independent(self) -> None:
        practical = self.service.create_course(self.db, CourseCreate(
            course_code="CCDT", course_name="Community Centered Design Thinking",
            offering_department_id=self.active_department.id, course_type="PRACTICAL",
            weekly_periods=3, grouping_mode="GROUPED", default_group_count=2,
            session_duration=3, sessions_per_week=1,
            venue_requirement="CLASSROOM_ONLY",
        ))
        self.assertEqual(practical.grouping_mode, "GROUPED")
        self.assertEqual(practical.session_duration, 3)
        self.assertEqual(practical.venue_requirement, "CLASSROOM_ONLY")
        self.assertIsNone(practical.default_laboratory_id)
        self.assertIsNone(practical.lab_session_duration)

        flexible = self.service.create_course(self.db, CourseCreate(
            course_code="CCDT-FLEX", course_name="Flexible CCDT",
            offering_department_id=self.active_department.id, course_type="PRACTICAL",
            weekly_periods=4, grouping_mode="GROUPED", default_group_count=2,
            session_duration=2, sessions_per_week=2,
            venue_requirement="CLASSROOM_OR_LABORATORY",
        ))
        self.assertIsNone(flexible.default_laboratory_id)

        full_section = self.service.create_course(self.db, CourseCreate(
            course_code="CCDT-FULL", course_name="Full-section CCDT",
            offering_department_id=self.active_department.id, course_type="PRACTICAL",
            weekly_periods=3, grouping_mode="FULL_SECTION", default_group_count=1,
            session_duration=3, sessions_per_week=1,
            venue_requirement="CLASSROOM_ONLY",
        ))
        self.assertEqual(full_section.default_group_count, 1)

    def test_generic_course_validation_rejects_inconsistent_properties(self) -> None:
        with self.assertRaises(HTTPException) as pattern:
            self.service.create_course(self.db, CourseCreate(
                course_code="BAD-PATTERN", course_name="Bad Pattern",
                offering_department_id=self.active_department.id, course_type="PRACTICAL",
                weekly_periods=3, session_duration=2, sessions_per_week=2,
                grouping_mode="FULL_SECTION", default_group_count=1,
                venue_requirement="CLASSROOM_ONLY",
            ))
        self.assertEqual(pattern.exception.status_code, 422)
        with self.assertRaises(HTTPException) as venue:
            self.service.create_course(self.db, CourseCreate(
                course_code="BAD-VENUE", course_name="Bad Venue",
                offering_department_id=self.active_department.id, course_type="PRACTICAL",
                weekly_periods=3, session_duration=3, sessions_per_week=1,
                grouping_mode="GROUPED", default_group_count=2,
                venue_requirement="LABORATORY_ONLY",
            ))
        self.assertEqual(venue.exception.status_code, 422)

    def test_weekly_periods_are_per_group_and_never_multiplied_by_group_count(self) -> None:
        course = self.service.create_course(self.db, CourseCreate(
            course_code="GROUP-CONTACT", course_name="Grouped Contact Pattern",
            offering_department_id=self.active_department.id, course_type="PRACTICAL",
            weekly_periods=3, session_duration=3, sessions_per_week=1,
            grouping_mode="GROUPED", default_group_count=6,
            venue_requirement="CLASSROOM_ONLY",
        ))
        self.assertEqual(course.weekly_periods, 3)
        self.assertEqual(course.default_group_count, 6)
        with self.assertRaises(HTTPException) as multiplied:
            self.service.create_course(self.db, CourseCreate(
                course_code="GROUP-MULTIPLIED", course_name="Incorrect Multiplied Pattern",
                offering_department_id=self.active_department.id, course_type="PRACTICAL",
                weekly_periods=18, session_duration=3, sessions_per_week=1,
                grouping_mode="GROUPED", default_group_count=6,
                venue_requirement="CLASSROOM_ONLY",
            ))
        self.assertIn("session duration multiplied by sessions per week", str(multiplied.exception.detail))

    def test_seed_permissions_are_idempotent(self) -> None:
        original_session_local = seed_script.SessionLocal
        seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try:
            seed_script.seed()
            seed_script.seed()
        finally:
            seed_script.SessionLocal = original_session_local
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Course)), 0)
        for role_name in ("Administrator", "Timetable Coordinator", "HOD"):
            role = self.db.scalar(select(Role).where(Role.name == role_name))
            permissions = {(permission.resource, permission.action) for permission in role.permissions}
            self.assertTrue({("courses", "read"), ("courses", "manage")} <= permissions)

    def test_explicit_laboratory_eligibility_preference_and_cross_department_rules(self) -> None:
        alternatives = []
        for index in range(2, 7):
            laboratory = Laboratory(laboratory_code=f"CSELAB{index}", laboratory_name=f"CSE Laboratory {index}", room_number=f"L10{index}", owning_department_id=self.active_department.id)
            self.db.add(laboratory); alternatives.append(laboratory)
        cross_department = Laboratory(laboratory_code="ECELAB", laboratory_name="ECE Laboratory", room_number="E101", owning_department_id=self.inactive_department.id, is_shareable_across_departments=False)
        self.db.add(cross_department); self.db.commit()

        eligible_ids = [self.laboratory.id, *[laboratory.id for laboratory in alternatives]]
        course = self.service.create_course(self.db, CourseCreate(
            course_code="A9301", course_name="Engineering Graphics", offering_department_id=self.active_department.id,
            course_type="PRACTICAL", weekly_periods=3, session_duration=3, sessions_per_week=1,
            venue_requirement="CLASSROOM_OR_LABORATORY", eligible_laboratory_ids=eligible_ids,
            default_laboratory_id=self.laboratory.id,
        ))
        self.assertEqual(course.eligible_laboratory_ids, eligible_ids)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CourseEligibleLaboratory).where(CourseEligibleLaboratory.course_id == course.id)), 6)

        with self.assertRaises(HTTPException) as preferred:
            self.service.create_course(self.db, CourseCreate(
                course_code="BAD-PREF", course_name="Bad Preference", offering_department_id=self.active_department.id,
                course_type="PRACTICAL", weekly_periods=3, session_duration=3, sessions_per_week=1,
                venue_requirement="CLASSROOM_OR_LABORATORY", eligible_laboratory_ids=[alternatives[0].id],
                default_laboratory_id=self.laboratory.id,
            ))
        self.assertEqual(preferred.exception.status_code, 422)
        with self.assertRaises(HTTPException) as sharing:
            self.service.create_course(self.db, CourseCreate(
                course_code="BAD-SHARE", course_name="Bad Sharing", offering_department_id=self.active_department.id,
                course_type="LABORATORY", weekly_periods=3, session_duration=3, sessions_per_week=1,
                eligible_laboratory_ids=[cross_department.id],
            ))
        self.assertEqual(sharing.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
