"""Integration coverage for deterministic solver-input snapshots."""

import json
import os
import unittest
from datetime import date, time
from uuid import UUID

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission, Role, User
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.departments.models import Department
from app.modules.facilities.models import Classroom, Laboratory
from app.modules.facilities_constraints.models import LaboratoryAvailabilityBlock, SectionClassroomAssignment
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.faculty_scheduling.models import FacultyAvailability, FacultySchedulingPolicy
from app.modules.laboratory_batches.models import LaboratoryBatchConfiguration, StudentBatch
from app.modules.programs.models import Program
from app.modules.schedule_configuration.models import PeriodTiming, WorkingDay
from app.modules.sections.models import Section
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.models import SolverInputSnapshot, Timetable, TimetableVersion
from app.modules.timetables.service import solver_input_builder
from tests.facilities_test_support import create_facilities_test_context


class SolverInputBuilderTests(unittest.TestCase):
    def setUp(self):
        self.ctx = create_facilities_test_context()
        db = self.ctx.session_factory()
        try:
            solver_permissions = [
                Permission(resource="solver_inputs", action="read"),
                Permission(resource="solver_inputs", action="build"),
            ]
            validation_permissions = [
                Permission(resource="timetable_validation", action="read"),
                Permission(resource="timetable_validation", action="run"),
            ]
            db.add_all(solver_permissions + validation_permissions)
            db.flush()
            roles = {role.name: role for role in db.scalars(select(Role)).all()}
            roles["Administrator"].permissions.extend(solver_permissions + validation_permissions)
            roles["Timetable Coordinator"].permissions.extend(solver_permissions)
            roles["HOD"].permissions.append(solver_permissions[0])
            administrator = db.scalar(select(User).where(User.email == "admin.test@vce.ac.in"))

            self.term = AcademicTerm(
                academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1,
                start_date=date(2026, 7, 1), end_date=date(2026, 11, 1), is_active=True,
            )
            program = Program(
                department_id=self.ctx.active_department.id, program_code="TST-UG",
                program_name="Test Program", degree_type="UG", duration_years=4,
            )
            db.add_all([self.term, program])
            db.flush()
            self.section = Section(
                program_id=program.id, academic_term_id=self.term.id, section_name="A",
                section_code="TST-A", student_strength=72,
            )
            classroom = Classroom(
                room_number="T-101", room_name="Primary", owning_department_id=self.ctx.active_department.id,
                is_primary_classroom=True,
            )
            self.classroom = classroom
            self.laboratory = Laboratory(
                laboratory_code="TST-LAB", laboratory_name="Test Laboratory", room_number="T-201",
                owning_department_id=self.ctx.active_department.id, availability_mode="EXCEPT_BLOCKED",
                is_available_all_periods=False,
            )
            db.add_all([self.section, classroom, self.laboratory])
            db.flush()
            db.add(SectionClassroomAssignment(
                section_id=self.section.id, classroom_id=classroom.id,
                academic_term_id=self.term.id, is_primary=True,
            ))

            # Deliberately insert Z before A; the snapshot must still order by course code.
            self.lab_course = Course(
                course_code="Z-LAB", course_name="Laboratory", offering_department_id=self.ctx.active_department.id,
                course_type="LABORATORY", weekly_periods=4, lab_session_duration=2,
                lab_sessions_per_week=2, default_lab_group_count=2, default_laboratory_id=self.laboratory.id,
                counts_toward_workload=True,
            )
            self.theory_course = Course(
                course_code="A-THEORY", course_name="Theory", offering_department_id=self.ctx.active_department.id,
                course_type="THEORY", weekly_periods=4, counts_toward_workload=True,
            )
            db.add_all([self.lab_course, self.theory_course])
            db.flush()
            self.lab_offering = CourseOffering(
                course_id=self.lab_course.id, section_id=self.section.id, academic_term_id=self.term.id,
            )
            theory_offering = CourseOffering(
                course_id=self.theory_course.id, section_id=self.section.id, academic_term_id=self.term.id,
            )
            self.theory_offering = theory_offering
            db.add_all([self.lab_offering, theory_offering])
            db.flush()

            self.faculty = Faculty(
                faculty_code="TST001", full_name="Test Faculty", department_id=self.ctx.active_department.id,
                designation="Assistant Professor", institutional_email="solver.faculty@vce.ac.in",
                minimum_weekly_workload=4, maximum_weekly_workload=18, maximum_periods_per_day=5,
            )
            db.add(self.faculty)
            db.flush()
            db.add_all([
                TheoryFacultyAllocation(course_offering_id=theory_offering.id, faculty_id=self.faculty.id),
                LaboratoryFacultyAllocation(
                    course_offering_id=self.lab_offering.id, faculty_id=self.faculty.id, role_type="MAIN",
                ),
            ])
            self.availability = FacultyAvailability(
                faculty_id=self.faculty.id, academic_term_id=self.term.id, day_of_week="Monday",
                period_number=1, availability_type="preferred", reason="Initial preference",
            )
            db.add_all([
                self.availability,
                FacultySchedulingPolicy(
                    faculty_id=self.faculty.id, academic_term_id=self.term.id,
                    maximum_periods_per_day=5, preferred_working_days=["Monday", "Tuesday"],
                ),
                StudentBatch(section_id=self.section.id, batch_name="A1", sequence_number=1, roll_number_start=1, roll_number_end=24, student_count=24),
                StudentBatch(section_id=self.section.id, batch_name="A2", sequence_number=2, roll_number_start=25, roll_number_end=48, student_count=24),
                StudentBatch(section_id=self.section.id, batch_name="A3", sequence_number=3, roll_number_start=49, roll_number_end=72, student_count=24),
                LaboratoryBatchConfiguration(
                    course_offering_id=self.lab_offering.id, section_id=self.section.id, number_of_groups=3,
                ),
            ])
            self.working_day = WorkingDay(day_name="Monday", sequence_number=1)
            db.add_all([
                self.working_day,
                WorkingDay(day_name="Tuesday", sequence_number=2),
                WorkingDay(day_name="Wednesday", sequence_number=3),
                WorkingDay(day_name="Thursday", sequence_number=4),
                WorkingDay(day_name="Friday", sequence_number=5),
                WorkingDay(day_name="Saturday", sequence_number=6),
            ])
            db.flush()
            timing_patterns = {
                "FIRST_YEAR": {1: (1, None), 2: (2, None), 3: (3, None), 4: (None, "LUNCH"), 5: (4, None), 6: (5, None), 7: (None, "SHORT_BREAK"), 8: (6, None), 9: (7, None)},
                "HIGHER_YEAR": {1: (1, None), 2: (2, None), 3: (None, "SHORT_BREAK"), 4: (3, None), 5: (4, None), 6: (None, "LUNCH"), 7: (5, None), 8: (6, None), 9: (7, None)},
            }
            timings = []
            for schedule_type, pattern in timing_patterns.items():
                for sequence_number, (period_number, break_type) in pattern.items():
                    timings.append(PeriodTiming(
                        schedule_type=schedule_type, period_number=period_number,
                        start_time=time(9, 10), end_time=time(10, 0), duration_minutes=50,
                        is_instructional=period_number is not None, break_type=break_type,
                        sequence_number=sequence_number,
                    ))
            db.add_all(timings)
            self.block = LaboratoryAvailabilityBlock(
                laboratory_id=self.laboratory.id, academic_term_id=self.term.id,
                working_day_id=self.working_day.id, period_number=7, reason="Maintenance",
            )
            db.add(self.block)

            # This complete but unrelated branch must not leak into a SECTION snapshot.
            other_department = Department(department_code="OTH", department_name="Other", short_name="OTH")
            db.add(other_department)
            db.flush()
            other_program = Program(
                department_id=other_department.id, program_code="OTH-UG", program_name="Other Program",
                degree_type="UG", duration_years=4,
            )
            db.add(other_program)
            db.flush()
            other_section = Section(
                program_id=other_program.id, academic_term_id=self.term.id, section_name="B",
                section_code="OTH-B", student_strength=60,
            )
            self.other_section = other_section
            db.add(other_section)

            self.run = ValidationRun(
                academic_term_id=self.term.id, scope_type="SECTION", section_id=self.section.id,
                status="PASSED", total_checks=1, passed_checks=1, failed_checks=0, warning_checks=0,
                created_by=administrator.id,
            )
            db.add(self.run)
            db.flush()
            self.timetable = Timetable(
                academic_term_id=self.term.id, scope_type="SECTION", section_id=self.section.id,
                name="Solver Test", status="DRAFT", created_by=administrator.id,
            )
            db.add(self.timetable)
            db.flush()
            self.version = TimetableVersion(
                timetable_id=self.timetable.id, version_number=1, source_type="GENERATED",
                validation_run_id=self.run.id, solver_status="NOT_STARTED", is_active=True,
                is_locked=False, created_by=administrator.id,
            )
            db.add(self.version)
            db.flush()
            self.timetable.active_version_id = self.version.id
            db.commit()
        finally:
            db.close()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.ctx.close()

    def test_build_reuses_identical_snapshot_and_marks_ready(self):
        url = f"/api/v1/timetable-versions/{self.version.id}/build-solver-input"
        first = self.client.post(url, headers=self.ctx.headers["administrator"])
        second = self.client.post(url, headers=self.ctx.headers["administrator"])
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertIsNotNone(first.json()["created_at"])
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["input_hash"], second.json()["input_hash"])
        db = self.ctx.session_factory()
        try:
            self.assertEqual(db.scalar(select(func.count()).select_from(SolverInputSnapshot)), 1)
            self.assertEqual(db.get(TimetableVersion, self.version.id).solver_status, "READY")
        finally:
            db.close()

    def test_snapshot_is_scoped_safe_and_deterministically_ordered(self):
        response = self.client.post(
            f"/api/v1/timetable-versions/{self.version.id}/build-solver-input",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        snapshot = response.json()["snapshot_json"]
        self.assertEqual([item["course_code"] for item in snapshot["course_offerings"]], ["A-THEORY", "Z-LAB"])
        laboratory_offering = next(item for item in snapshot["course_offerings"] if item["course_type"] == "LABORATORY")
        self.assertEqual(laboratory_offering["course_default_lab_group_count"], 2)
        self.assertEqual(laboratory_offering["effective_lab_group_count"], 3)
        self.assertNotIn("lab_batch_count", laboratory_offering)
        self.assertEqual([item["section_code"] for item in snapshot["sections"]], ["TST-A"])
        serialized = json.dumps(snapshot)
        self.assertNotIn("OTH-B", serialized)
        self.assertNotIn("password_hash", serialized)
        self.assertNotIn("admin.test@vce.ac.in", serialized)
        self.assertEqual(snapshot["locked_entries"], [])

    def test_relevant_data_changes_create_new_hashes(self):
        url = f"/api/v1/timetable-versions/{self.version.id}/build-solver-input"
        hashes = [self.client.post(url, headers=self.ctx.headers["administrator"]).json()["input_hash"]]
        db = self.ctx.session_factory()
        try:
            db.get(Course, self.theory_course.id).weekly_periods = 5
            db.commit()
        finally:
            db.close()
        hashes.append(self.client.post(url, headers=self.ctx.headers["administrator"]).json()["input_hash"])
        db = self.ctx.session_factory()
        try:
            db.get(FacultyAvailability, self.availability.id).reason = "Changed preference"
            db.commit()
        finally:
            db.close()
        hashes.append(self.client.post(url, headers=self.ctx.headers["administrator"]).json()["input_hash"])
        db = self.ctx.session_factory()
        try:
            db.get(LaboratoryAvailabilityBlock, self.block.id).reason = "Changed maintenance"
            db.commit()
        finally:
            db.close()
        hashes.append(self.client.post(url, headers=self.ctx.headers["administrator"]).json()["input_hash"])
        self.assertEqual(len(set(hashes)), 4)

    def test_practical_activity_allocation_is_snapshotted_and_changes_hash(self):
        db = self.ctx.session_factory()
        try:
            practical = Course(course_code="A9021", course_name="Community Centered Design Thinking", offering_department_id=self.ctx.active_department.id, course_type="PRACTICAL", weekly_periods=3, grouping_mode="GROUPED", default_group_count=3, session_duration=3, sessions_per_week=1, venue_requirement="CLASSROOM_ONLY", counts_toward_workload=True)
            replacement = Faculty(faculty_code="TST002", full_name="Replacement Faculty", department_id=self.ctx.active_department.id, designation="Assistant Professor", institutional_email="replacement.faculty@vce.ac.in", minimum_weekly_workload=0, maximum_weekly_workload=18)
            db.add_all([practical,replacement]);db.flush()
            offering=CourseOffering(course_id=practical.id,section_id=self.section.id,academic_term_id=self.term.id);db.add(offering);db.flush()
            allocation=LaboratoryFacultyAllocation(course_offering_id=offering.id,faculty_id=self.faculty.id,role_type="MAIN",minimum_sessions_per_week=1,maximum_sessions_per_week=1)
            db.add_all([allocation,LaboratoryBatchConfiguration(course_offering_id=offering.id,section_id=self.section.id,number_of_groups=3)]);db.commit()
            offering_id,allocation_id,replacement_id=offering.id,allocation.id,replacement.id
        finally:db.close()
        url=f"/api/v1/timetable-versions/{self.version.id}/build-solver-input"
        first=self.client.post(url,headers=self.ctx.headers["administrator"]);self.assertEqual(first.status_code,201,first.text)
        snapshot=first.json()["snapshot_json"]
        self.assertTrue(any(item["course_offering_id"]==str(offering_id) and item["faculty_id"]==str(self.faculty.id) and item["role_type"]=="MAIN" for item in snapshot["laboratory_faculty_allocations"]))
        self.assertFalse(any(item["course_offering_id"]==str(offering_id) for item in snapshot["theory_faculty_allocations"]))
        db=self.ctx.session_factory()
        try:db.get(LaboratoryFacultyAllocation,allocation_id).faculty_id=replacement_id;db.commit()
        finally:db.close()
        second=self.client.post(url,headers=self.ctx.headers["administrator"]);self.assertNotEqual(first.json()["input_hash"],second.json()["input_hash"])

    def test_build_eligibility_rejections(self):
        db = self.ctx.session_factory()
        try:
            run = db.get(ValidationRun, self.run.id)
            version = db.get(TimetableVersion, self.version.id)
            timetable = db.get(Timetable, self.timetable.id)
            run.status = "FAILED"
            db.commit()
            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, self.version.id)
            self.assertEqual(rejected.exception.status_code, 422)

            run.status = "PASSED"
            version.is_locked = True
            db.commit()
            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, self.version.id)
            self.assertEqual(rejected.exception.status_code, 409)

            version.is_locked = False
            version.is_active = False
            db.commit()
            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, self.version.id)
            self.assertEqual(rejected.exception.status_code, 409)

            version.is_active = True
            timetable.status = "ARCHIVED"
            db.commit()
            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, self.version.id)
            self.assertEqual(rejected.exception.status_code, 409)

            timetable.status = "DRAFT"
            run.scope_type = "COLLEGE"
            run.section_id = None
            db.commit()
            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, self.version.id)
            self.assertEqual(rejected.exception.status_code, 422)

            with self.assertRaises(HTTPException) as rejected:
                solver_input_builder.build(db, UUID("00000000-0000-0000-0000-000000000000"))
            self.assertEqual(rejected.exception.status_code, 404)
        finally:
            db.close()

    def test_endpoint_authorization_and_latest_snapshot(self):
        build_url = f"/api/v1/timetable-versions/{self.version.id}/build-solver-input"
        get_url = f"/api/v1/timetable-versions/{self.version.id}/solver-input"
        self.assertEqual(self.client.get(get_url, headers=self.ctx.headers["administrator"]).status_code, 404)
        self.assertEqual(self.client.post(build_url, headers=self.ctx.headers["hod"]).status_code, 403)
        self.assertEqual(self.client.post(build_url, headers=self.ctx.headers["unauthorized"]).status_code, 403)
        built = self.client.post(build_url, headers=self.ctx.headers["coordinator"])
        self.assertEqual(built.status_code, 201, built.text)
        self.assertEqual(self.client.get(get_url, headers=self.ctx.headers["hod"]).status_code, 200)
        self.assertEqual(self.client.get(get_url, headers=self.ctx.headers["unauthorized"]).status_code, 403)

    def test_batch_count_override_is_a_persisted_warning_when_three_batches_exist(self):
        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "SECTION", "section_id": str(self.section.id)},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "WARNING")
        self.assertEqual(response.json()["failed_checks"], 0)
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{response.json()['id']}/issues?issue_code=LAB_BATCH_COUNT_OVERRIDE",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(issues.status_code, 200, issues.text)
        self.assertEqual(issues.json()["total"], 1)
        self.assertEqual(issues.json()["items"][0]["details"]["course_default_lab_group_count"], 2)
        self.assertEqual(issues.json()["items"][0]["details"]["effective_lab_group_count"], 3)

    def test_validator_reports_selected_period_and_mode_conflicts(self):
        db = self.ctx.session_factory()
        try:
            laboratory = db.get(Laboratory, self.laboratory.id)
            laboratory.availability_mode = "ONLY_SELECTED"
            laboratory.is_available_all_periods = False
            db.commit()
        finally:
            db.close()
        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "SECTION", "section_id": str(self.section.id)},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{response.json()['id']}/issues",
            headers=self.ctx.headers["administrator"],
        ).json()["items"]
        codes = {issue["issue_code"] for issue in issues}
        self.assertIn("LAB_AVAILABILITY_CONFLICT", codes)
        self.assertIn("LAB_SELECTED_PERIODS_EMPTY", codes)
        self.assertIn("LAB_NO_AVAILABLE_PERIODS", codes)

    def test_validator_accepts_nonempty_selected_period_configuration(self):
        db = self.ctx.session_factory()
        try:
            laboratory = db.get(Laboratory, self.laboratory.id)
            laboratory.availability_mode = "ONLY_SELECTED"
            laboratory.is_available_all_periods = False
            block = db.get(LaboratoryAvailabilityBlock, self.block.id)
            block.availability_type = "ALLOWED"
            db.commit()
        finally:
            db.close()
        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "SECTION", "section_id": str(self.section.id)},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{response.json()['id']}/issues",
            headers=self.ctx.headers["administrator"],
        ).json()["items"]
        codes = {issue["issue_code"] for issue in issues}
        self.assertNotIn("LAB_AVAILABILITY_CONFLICT", codes)
        self.assertNotIn("LAB_SELECTED_PERIODS_EMPTY", codes)
        self.assertNotIn("LAB_NO_AVAILABLE_PERIODS", codes)

    def test_two_active_batches_fail_against_effective_count_three(self):
        db = self.ctx.session_factory()
        try:
            third = db.scalar(select(StudentBatch).where(StudentBatch.section_id == self.section.id, StudentBatch.sequence_number == 3))
            third.is_active = False
            db.commit()
        finally:
            db.close()
        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "SECTION", "section_id": str(self.section.id)},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "FAILED")
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{response.json()['id']}/issues",
            headers=self.ctx.headers["administrator"],
        ).json()["items"]
        self.assertIn("STUDENT_BATCHES_INCOMPLETE", {issue["issue_code"] for issue in issues})
        self.assertIn("LAB_BATCH_COUNT_OVERRIDE", {issue["issue_code"] for issue in issues})

    def test_six_active_groups_match_generic_offering_configuration(self):
        db = self.ctx.session_factory()
        try:
            for batch in db.scalars(select(StudentBatch).where(StudentBatch.section_id == self.section.id)):
                batch.is_active = False
            for sequence in range(1, 7):
                start = (sequence - 1) * 12 + 1
                db.add(StudentBatch(section_id=self.section.id, batch_name=f"A{sequence}", sequence_number=sequence, roll_number_start=start, roll_number_end=start + 11, student_count=12))
            configuration = db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == self.lab_offering.id))
            configuration.number_of_groups = 6
            db.commit()
        finally:
            db.close()

        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "SECTION", "section_id": str(self.section.id)},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{response.json()['id']}/issues",
            headers=self.ctx.headers["administrator"],
        ).json()["items"]
        self.assertNotIn("STUDENT_BATCHES_INCOMPLETE", {issue["issue_code"] for issue in issues})
        self.assertIn("LAB_BATCH_COUNT_OVERRIDE", {issue["issue_code"] for issue in issues})

        snapshot = self.client.post(
            f"/api/v1/timetable-versions/{self.version.id}/build-solver-input",
            headers=self.ctx.headers["administrator"],
        ).json()["snapshot_json"]
        laboratory = next(item for item in snapshot["course_offerings"] if item["course_type"] == "LABORATORY")
        self.assertEqual(laboratory["effective_lab_group_count"], 6)
        self.assertEqual(len(snapshot["student_batches"]), 6)


if __name__ == "__main__":
    unittest.main()
