"""Generic synchronized laboratory rotation service, solver, and review tests."""
import unittest
from collections import Counter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.course_offerings.models import CourseOffering
from app.modules.authentication.models import Permission, Role
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.facilities.models import Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.faculty_allocations.workload import configured_faculty_workloads
from app.modules.laboratory_batches.models import (
    LaboratoryBatchConfiguration,
    LaboratoryRotationAssignment,
    LaboratoryRotationBlock,
    StudentBatch,
)
from app.modules.laboratory_batches.schemas import RotationGenerateRequest
from app.modules.laboratory_batches.services import service
from app.modules.timetables.models import TimetableEntry
from tests import test_solver_input_builder as solver_support


class LaboratoryRotationEngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready")
        self.fixture.setUp()
        self.ctx = self.fixture.ctx
        db = self.ctx.session_factory()
        try:
            permissions = [Permission(resource="timetable_solver", action="read"), Permission(resource="timetable_solver", action="run"), Permission(resource="timetable_entries", action="move")]
            db.add_all(permissions); db.flush()
            administrator_role = db.scalar(select(Role).where(Role.name == "Administrator"))
            administrator_role.permissions.extend(permissions)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.fixture.tearDown()

    def _set_group_count(self, count):
        db = self.ctx.session_factory()
        try:
            batches = list(db.scalars(select(StudentBatch).where(StudentBatch.section_id == self.fixture.section.id).order_by(StudentBatch.sequence_number)))
            if len(batches) < count:
                db.close()
                db = self.ctx.session_factory()
                service.batches(db, self.fixture.section.id, count, overwrite=True)
                db.close()
                db = self.ctx.session_factory()
                batches = list(db.scalars(select(StudentBatch).where(StudentBatch.section_id == self.fixture.section.id, StudentBatch.is_active.is_(True)).order_by(StudentBatch.sequence_number)))
            for batch in batches:
                batch.is_active = batch.sequence_number <= count
            configuration = db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == self.fixture.lab_offering.id))
            configuration.number_of_groups = count
            db.commit()
        finally:
            db.close()

    def _add_lab(self, suffix, group_count):
        db = self.ctx.session_factory()
        try:
            laboratory = Laboratory(laboratory_code=f"ROT-LAB-{suffix}", laboratory_name=f"Rotation Laboratory {suffix}", room_number=f"R-{suffix}", owning_department_id=self.ctx.active_department.id)
            faculty = Faculty(faculty_code=f"ROT{suffix}", full_name=f"Rotation Faculty {suffix}", department_id=self.ctx.active_department.id, designation="Assistant Professor", institutional_email=f"rotation.{suffix.lower()}@vce.ac.in", minimum_weekly_workload=0, maximum_weekly_workload=18)
            db.add_all([laboratory, faculty]); db.flush()
            course = Course(course_code=f"ROT-{suffix}", course_name=f"Rotation Lab {suffix}", offering_department_id=self.ctx.active_department.id, course_type="LABORATORY", weekly_periods=4, lab_session_duration=2, lab_sessions_per_week=2, default_lab_group_count=group_count, default_laboratory_id=laboratory.id, counts_toward_workload=True)
            db.add(course); db.flush()
            offering = CourseOffering(course_id=course.id, section_id=self.fixture.section.id, academic_term_id=self.fixture.term.id)
            db.add(offering); db.flush()
            db.add_all([LaboratoryBatchConfiguration(course_offering_id=offering.id, section_id=self.fixture.section.id, number_of_groups=group_count), LaboratoryFacultyAllocation(course_offering_id=offering.id, faculty_id=faculty.id, role_type="MAIN")])
            db.commit()
            return offering.id
        finally:
            db.close()

    def _generate(self, offering_ids, code="ROTATION"):
        db = self.ctx.session_factory()
        try:
            payload = RotationGenerateRequest.model_construct(section_id=self.fixture.section.id, academic_term_id=self.fixture.term.id, rotation_code=code, course_offering_ids=offering_ids, student_group_ids=None, overwrite=False) if len(offering_ids) < 2 else RotationGenerateRequest(section_id=self.fixture.section.id, academic_term_id=self.fixture.term.id, rotation_code=code, course_offering_ids=offering_ids)
            return service.generate_rotation(db, payload)
        finally:
            db.close()

    def _set_patterns(self, offering_ids, duration, sessions):
        db = self.ctx.session_factory()
        try:
            for offering in db.scalars(select(CourseOffering).where(CourseOffering.id.in_(offering_ids))):
                course = db.get(Course, offering.course_id)
                course.weekly_periods = duration * sessions
                course.session_duration = course.lab_session_duration = duration
                course.sessions_per_week = course.lab_sessions_per_week = sessions
            db.commit()
        finally:
            db.close()

    def _add_practical(self, suffix, group_count):
        db = self.ctx.session_factory()
        try:
            laboratory = Laboratory(laboratory_code=f"ROT-PR-{suffix}", laboratory_name=f"Practical Laboratory {suffix}", room_number=f"P-{suffix}", owning_department_id=self.ctx.active_department.id)
            faculty = Faculty(faculty_code=f"PR{suffix}", full_name=f"Practical Faculty {suffix}", department_id=self.ctx.active_department.id, designation="Assistant Professor", institutional_email=f"practical.{suffix.lower()}@vce.ac.in", minimum_weekly_workload=0, maximum_weekly_workload=18)
            db.add_all([laboratory, faculty]); db.flush()
            course = Course(course_code=f"PR-{suffix}", course_name=f"Rotation Practical {suffix}", offering_department_id=self.ctx.active_department.id, course_type="PRACTICAL", weekly_periods=3, grouping_mode="GROUPED", default_group_count=group_count, session_duration=3, sessions_per_week=1, venue_requirement="CLASSROOM_OR_LABORATORY", counts_toward_workload=True)
            db.add(course); db.flush()
            offering = CourseOffering(course_id=course.id, section_id=self.fixture.section.id, academic_term_id=self.fixture.term.id)
            db.add(offering); db.flush()
            db.add_all([CourseEligibleLaboratory(course_id=course.id, laboratory_id=laboratory.id), LaboratoryBatchConfiguration(course_offering_id=offering.id, section_id=self.fixture.section.id, number_of_groups=group_count), TheoryFacultyAllocation(course_offering_id=offering.id, faculty_id=faculty.id)])
            db.commit()
            return offering.id
        finally:
            db.close()

    def test_two_groups_two_laboratories_swap(self):
        self._set_group_count(2); second = self._add_lab("B", 2)
        independent = self._add_lab("FULL2", 1)
        matrix = self._generate([self.fixture.lab_offering.id, second])
        self.assertEqual(len(matrix["blocks"]), 4)
        self.assertTrue(all(len(block["assignments"]) == 2 for block in matrix["blocks"]))
        pairs = {(row.batch_id, row.course_offering_id) for block in matrix["blocks"] for row in block["assignments"]}
        self.assertEqual(len(pairs), 4)
        self.assertTrue(all(sum(row.batch_id == batch and row.course_offering_id == offering for block in matrix["blocks"] for row in block["assignments"]) == 2 for batch, offering in pairs))
        self.assertNotIn(independent, matrix["course_offering_ids"])

    def test_two_groups_three_laboratories_cyclic(self):
        self._set_group_count(2); second = self._add_lab("B", 2); third = self._add_lab("C", 2)
        self._set_patterns([self.fixture.lab_offering.id, second, third], 3, 1)
        matrix = self._generate([self.fixture.lab_offering.id, second, third])
        self.assertEqual(len(matrix["blocks"]), 3)
        self.assertTrue(all(len(block["assignments"]) == 2 for block in matrix["blocks"]))
        self.assertEqual(len({(row.batch_id, row.course_offering_id) for block in matrix["blocks"] for row in block["assignments"]}), 6)
        self.assertEqual(len(matrix["blocks"]) * 3, 9)

    def test_three_groups_three_laboratories_and_mixed_independent_lab(self):
        self._set_group_count(3)
        second = self._add_lab("B", 3); third = self._add_lab("C", 3)
        independent = self._add_lab("FULL", 1)
        self._set_patterns([self.fixture.lab_offering.id, second, third], 3, 1)
        matrix = self._generate([self.fixture.lab_offering.id, second, third])
        self.assertEqual(len(matrix["blocks"]), 3)
        self.assertTrue(all(len(block["assignments"]) == 3 for block in matrix["blocks"]))
        self.assertEqual(len({(row.batch_id, row.course_offering_id) for block in matrix["blocks"] for row in block["assignments"]}), 9)
        self.assertNotIn(independent, matrix["course_offering_ids"])

    def test_six_groups_six_laboratories_remain_generic(self):
        self._set_group_count(6)
        offerings = [self.fixture.lab_offering.id, *[self._add_lab(str(index), 6) for index in range(2, 7)]]
        self._set_patterns(offerings, 3, 1)
        matrix = self._generate(offerings, "SIX-WAY")
        self.assertEqual(len(matrix["blocks"]), 6)
        self.assertTrue(all(len(block["assignments"]) == 6 for block in matrix["blocks"]))
        self.assertEqual(len({(row.batch_id, row.course_offering_id) for block in matrix["blocks"] for row in block["assignments"]}), 36)

    def test_invalid_one_rotating_lab_and_mixed_group_counts(self):
        self._set_group_count(2)
        independent = self._add_lab("ONLYFULL", 1)
        with self.assertRaises(HTTPException) as single:
            self._generate([self.fixture.lab_offering.id])
        self.assertIn("ROTATION_REQUIRES_MULTIPLE_LABS", str(single.exception.detail))
        self.assertNotEqual(independent, self.fixture.lab_offering.id)
        mismatched = self._add_lab("THREE", 3)
        with self.assertRaises(HTTPException) as mixed:
            self._generate([self.fixture.lab_offering.id, mismatched], "MIXED")
        self.assertIn("ROTATION_GROUP_CONFIGURATION_MISMATCH", str(mixed.exception.detail))

    def test_solver_persists_synchronized_children_and_move_moves_whole_block(self):
        self._set_group_count(2); second = self._add_lab("B", 2)
        matrix = self._generate([self.fixture.lab_offering.id, second])
        build = self.fixture.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input", headers=self.ctx.headers["administrator"])
        self.assertEqual(build.status_code, 201, build.text)
        solve = self.fixture.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/solve", json={"time_limit_seconds": 10, "random_seed": 1}, headers=self.ctx.headers["administrator"])
        self.assertEqual(solve.status_code, 201, solve.text); self.assertIn(solve.json()["status"], {"FEASIBLE", "OPTIMAL"})
        db = self.ctx.session_factory()
        try:
            entries = list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id == self.fixture.version.id, TimetableEntry.laboratory_rotation_block_id.is_not(None)).order_by(TimetableEntry.laboratory_rotation_block_id, TimetableEntry.id)))
            self.assertEqual(len(entries), 8)
            grouped = {}
            for entry in entries: grouped.setdefault(entry.laboratory_rotation_block_id, []).append(entry)
            self.assertEqual(set(grouped), {UUID(str(block["id"])) for block in matrix["blocks"]})
            self.assertTrue(all(len(children) == 2 and len({(child.working_day_id, child.period_number) for child in children}) == 1 for children in grouped.values()))
            contact = Counter((entry.student_batch_id, entry.course_offering_id) for entry in entries)
            self.assertEqual(set(contact.values()), {2})
            self.assertTrue(all(sum(entry.session_length for entry in entries if (entry.student_batch_id, entry.course_offering_id) == pair) == 4 for pair in contact))
            target = entries[0]
            target_id = target.id
            target_block = target.laboratory_rotation_block_id
            day_id = target.working_day_id
            period = target.period_number
        finally:
            db.close()
        move = self.fixture.client.post(f"/api/v1/timetable-entries/{target_id}/move", json={"working_day_id": str(day_id), "period_number": period, "lock_after_move": False}, headers=self.ctx.headers["administrator"])
        self.assertEqual(move.status_code, 200, move.text)
        db = self.ctx.session_factory()
        try:
            siblings = list(db.scalars(select(TimetableEntry).where(TimetableEntry.laboratory_rotation_block_id == target_block)))
            self.assertTrue(all(entry.is_manual and not entry.is_locked for entry in siblings))
            self.assertEqual(len({(entry.working_day_id, entry.period_number) for entry in siblings}), 1)
        finally:
            db.close()

    def test_two_groups_two_three_period_activities_use_weekly_periods_three(self):
        self._set_group_count(2); second = self._add_lab("CONTACT", 2)
        db = self.ctx.session_factory()
        try:
            offering_ids = (self.fixture.lab_offering.id, second)
            for offering in db.scalars(select(CourseOffering).where(CourseOffering.id.in_(offering_ids))):
                course = db.get(Course, offering.course_id)
                course.weekly_periods = course.session_duration = course.lab_session_duration = 3
                course.sessions_per_week = course.lab_sessions_per_week = 1
            db.commit()
        finally:
            db.close()
        matrix = self._generate(list(offering_ids), "CONTACT-SEMANTICS")
        self.assertEqual(len(matrix["blocks"]), 2)
        db = self.ctx.session_factory()
        try:
            workload = configured_faculty_workloads(db, offering_ids=set(offering_ids), academic_term_id=self.fixture.term.id)
            rotation_faculty_ids = {row.main_faculty_id for block in matrix["blocks"] for row in block["assignments"]}
            self.assertTrue(all(workload[faculty_id] == 6 for faculty_id in rotation_faculty_ids))
        finally:
            db.close()
        build = self.fixture.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input", headers=self.ctx.headers["administrator"])
        self.assertEqual(build.status_code, 201, build.text)
        solve = self.fixture.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/solve", json={"time_limit_seconds": 10, "random_seed": 1}, headers=self.ctx.headers["administrator"])
        self.assertIn(solve.json()["status"], {"FEASIBLE", "OPTIMAL"}, solve.text)
        db = self.ctx.session_factory()
        try:
            entries = list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id == self.fixture.version.id, TimetableEntry.laboratory_rotation_block_id.is_not(None))))
            self.assertEqual(len(entries), 4)
            self.assertEqual({db.get(Course, db.get(CourseOffering, offering_id).course_id).weekly_periods for offering_id in offering_ids}, {3})
            contact = {(entry.student_batch_id, entry.course_offering_id): entry.session_length for entry in entries}
            self.assertEqual(len(contact), 4); self.assertEqual(set(contact.values()), {3})
            self.assertEqual(len({entry.laboratory_rotation_block_id for entry in entries}) * 3, 6)
            faculty_load = Counter(entry.faculty_id for entry in entries for _ in range(entry.session_length))
            laboratory_load = Counter(entry.laboratory_id for entry in entries for _ in range(entry.session_length))
            self.assertEqual(set(faculty_load.values()), {6}); self.assertEqual(set(laboratory_load.values()), {6})
        finally:
            db.close()

    def test_lab_and_lab_capable_practical_rotate_together(self):
        self._set_group_count(2); practical = self._add_practical("CCDT", 2)
        db = self.ctx.session_factory()
        try:
            course = db.get(Course, self.fixture.lab_course.id)
            course.weekly_periods = course.session_duration = course.lab_session_duration = 3
            course.sessions_per_week = course.lab_sessions_per_week = 1
            db.commit()
        finally:
            db.close()
        matrix = self._generate([self.fixture.lab_offering.id, practical], "LAB-PRACTICAL")
        self.assertEqual(len(matrix["blocks"]), 2)
        self.assertEqual(len({(row.batch_id, row.course_offering_id) for block in matrix["blocks"] for row in block["assignments"]}), 4)
