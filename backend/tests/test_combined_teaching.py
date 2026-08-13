"""Combined teaching API, accounting, persistence, and solver regressions."""

import os
import unittest
from uuid import uuid4
from sqlalchemy import select

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from app.modules.authentication.models import Permission, Role, User
from app.modules.combined_teaching.models import CombinedTeachingEvent, CombinedTeachingGroup
from app.modules.combined_teaching.schemas import CombinedTeachingGroupCreate
from app.modules.combined_teaching.service import combined_teaching_service
from app.modules.course_offerings.models import CourseOffering
from app.modules.facilities.models import Classroom
from app.modules.facilities_constraints.models import SectionClassroomAssignment
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import TheoryFacultyAllocation
from app.modules.faculty_allocations.services import faculty_allocation_service
from app.modules.sections.models import Section
from app.modules.timetables.models import TimetableEntry
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.review_schemas import TimetableEntryMove, VersionCopyRequest
from app.modules.timetables.review_service import review_service
from tests import test_solver_input_builder as solver_support


class CombinedTeachingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready")
        self.fixture.setUp(); self.ctx = self.fixture.ctx; self.client = self.fixture.client
        db = self.ctx.session_factory()
        try:
            permissions = [Permission(resource="combined_teaching_groups", action="read"), Permission(resource="combined_teaching_groups", action="manage"), Permission(resource="timetable_solver", action="read"), Permission(resource="timetable_solver", action="run"), Permission(resource="timetable_views", action="read")]
            db.add_all(permissions); db.flush()
            roles = {role.name: role for role in db.scalars(select(Role)).all()}
            for role in (roles["Administrator"], roles["Timetable Coordinator"], roles["HOD"]): role.permissions.extend(permissions[:2])
            roles["Administrator"].permissions.extend(permissions[2:]); roles["Timetable Coordinator"].permissions.extend(permissions[2:])
            program_id = self.fixture.section.program_id
            self.section_b = Section(program_id=program_id, academic_term_id=self.fixture.term.id, section_name="B", section_code="TST-B", student_strength=72)
            self.section_c = Section(program_id=program_id, academic_term_id=self.fixture.term.id, section_name="C", section_code="TST-C", student_strength=72)
            self.large_room = Classroom(room_number="1101", room_name="Common Hall", capacity=150, owning_department_id=self.ctx.active_department.id, is_shareable=True)
            self.room_c = Classroom(room_number="1203", room_name="Section C", capacity=80, owning_department_id=self.ctx.active_department.id)
            self.faculty_c = Faculty(faculty_code="TST002", full_name="Independent Faculty", department_id=self.ctx.active_department.id, designation="Professor", institutional_email="independent@vce.ac.in", minimum_weekly_workload=0, maximum_weekly_workload=18, maximum_periods_per_day=7)
            db.add_all([self.section_b, self.section_c, self.large_room, self.room_c, self.faculty_c]); db.flush()
            db.add_all([SectionClassroomAssignment(section_id=self.section_b.id, classroom_id=self.large_room.id, academic_term_id=self.fixture.term.id), SectionClassroomAssignment(section_id=self.section_c.id, classroom_id=self.room_c.id, academic_term_id=self.fixture.term.id)])
            self.offering_b = CourseOffering(course_id=self.fixture.theory_course.id, section_id=self.section_b.id, academic_term_id=self.fixture.term.id)
            self.offering_c = CourseOffering(course_id=self.fixture.theory_course.id, section_id=self.section_c.id, academic_term_id=self.fixture.term.id)
            db.add_all([self.offering_b, self.offering_c]); db.flush()
            db.add_all([TheoryFacultyAllocation(course_offering_id=self.offering_b.id, faculty_id=self.fixture.faculty.id), TheoryFacultyAllocation(course_offering_id=self.offering_c.id, faculty_id=self.faculty_c.id)])
            run = db.get(ValidationRun, self.fixture.run.id); run.scope_type = "PROGRAM"; run.section_id = None; run.program_id = program_id
            self.fixture.timetable.scope_type = "PROGRAM"; self.fixture.timetable.section_id = None; self.fixture.timetable.program_id = program_id; db.merge(self.fixture.timetable)
            db.commit()
        finally: db.close()

    def tearDown(self): self.fixture.tearDown()

    def payload(self, **changes):
        values = {"academic_term_id": self.fixture.term.id, "group_code": "DS-CSE-AB", "group_name": "Data Structures CSE-A + CSE-B", "course_id": self.fixture.theory_course.id, "faculty_id": self.fixture.faculty.id, "preferred_classroom_id": self.large_room.id, "course_offering_ids": [self.fixture.theory_offering.id, self.offering_b.id]}
        values.update(changes); return CombinedTeachingGroupCreate(**values)

    def test_api_lifecycle_readable_summary_capacity_and_permissions(self):
        body = self.payload().model_dump(mode="json")
        denied = self.client.post("/api/v1/combined-teaching-groups", json=body, headers=self.ctx.headers["unauthorized"]); self.assertEqual(denied.status_code, 403)
        created = self.client.post("/api/v1/combined-teaching-groups", json=body, headers=self.ctx.headers["administrator"]); self.assertEqual(created.status_code, 201, created.text)
        data = created.json(); self.assertEqual(data["combined_strength"], 144); self.assertEqual(data["venue_capacity"], 150); self.assertEqual(data["capacity_status"], "OK"); self.assertEqual([row["section_code"] for row in data["offerings"]], ["TST-A", "TST-B"])
        listed = self.client.get("/api/v1/combined-teaching-groups", headers=self.ctx.headers["hod"]); self.assertEqual(listed.status_code, 200); self.assertEqual(listed.json()["total"], 1)
        group_id = data["id"]; fetched = self.client.get(f"/api/v1/combined-teaching-groups/{group_id}", headers=self.ctx.headers["hod"]); self.assertEqual(fetched.status_code, 200)
        updated = self.client.put(f"/api/v1/combined-teaching-groups/{group_id}", json={"group_name": "Data Structures Common Class"}, headers=self.ctx.headers["coordinator"]); self.assertEqual(updated.status_code, 200); self.assertEqual(updated.json()["group_name"], "Data Structures Common Class")
        self.assertEqual(self.client.delete(f"/api/v1/combined-teaching-groups/{group_id}", headers=self.ctx.headers["coordinator"]).status_code, 204)
        restored = self.client.post(f"/api/v1/combined-teaching-groups/{group_id}/restore", headers=self.ctx.headers["coordinator"]); self.assertEqual(restored.status_code, 200)

    def test_compatibility_and_capacity_errors_are_explicit(self):
        db = self.ctx.session_factory()
        try:
            self.large_room.capacity = 100; db.merge(self.large_room); db.commit()
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_CAPACITY_EXCEEDED"): combined_teaching_service.create(db, self.payload())
            db.rollback(); room = db.get(Classroom, self.large_room.id); room.capacity = 150
            offering = db.get(CourseOffering, self.offering_b.id); offering.academic_term_id = uuid4()
            db.flush()
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_TERM_MISMATCH"): combined_teaching_service.create(db, self.payload(group_code="TERM-BAD"))
            db.rollback()
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_DUPLICATE_SECTION"): combined_teaching_service.create(db, self.payload(group_code="DUP", course_offering_ids=[self.fixture.theory_offering.id, self.fixture.theory_offering.id]))
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_COURSE_MISMATCH"): combined_teaching_service.create(db, self.payload(group_code="COURSE-BAD", course_offering_ids=[self.fixture.theory_offering.id, self.fixture.lab_offering.id]))
            offering = db.get(CourseOffering, self.offering_b.id); offering.weekly_periods_override = 3; db.flush()
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_SESSION_MISMATCH"): combined_teaching_service.create(db, self.payload(group_code="SESSION-BAD"))
            db.rollback(); section = db.get(Section, self.section_b.id); section.student_strength = 0; db.flush()
            with self.assertRaisesRegex(Exception, "COMBINED_TEACHING_SECTION_STRENGTH_MISSING"): combined_teaching_service.create(db, self.payload(group_code="STRENGTH-BAD"))
        finally: db.close()

    def test_three_section_group_is_generic_and_capacity_aware(self):
        db = self.ctx.session_factory()
        try:
            allocation = db.scalar(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id == self.offering_c.id)); allocation.faculty_id = self.fixture.faculty.id
            room = db.get(Classroom, self.large_room.id); room.capacity = 220; db.commit()
            created = combined_teaching_service.create(db, self.payload(group_code="DS-CSE-ABC", group_name="Data Structures A+B+C", course_offering_ids=[self.fixture.theory_offering.id, self.offering_b.id, self.offering_c.id]))
            self.assertEqual(created["combined_strength"], 216); self.assertEqual([row["section_code"] for row in created["offerings"]], ["TST-A", "TST-B", "TST-C"]); self.assertEqual(created["capacity_status"], "OK")
        finally: db.close()

    def test_solver_acceptance_accounting_views_atomic_operations_and_copy(self):
        db = self.ctx.session_factory()
        try:
            legacy = db.get(CourseOffering, self.offering_c.id); legacy.is_common_theory = True; legacy.common_theory_group_code = "LEGACY-TEXT-MUST-NOT-SCHEDULE"; db.commit()
            group = combined_teaching_service.create(db, self.payload()); group_id = group["id"]
        finally: db.close()
        build = self.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input", headers=self.ctx.headers["administrator"]); self.assertEqual(build.status_code, 201, build.text)
        snapshot = build.json()["snapshot_json"]; self.assertEqual(snapshot["combined_teaching_groups"][0]["combined_strength"], 144)
        self.assertTrue(all("is_common_theory" not in offering and "common_theory_group_code" not in offering for offering in snapshot["course_offerings"]))
        solve = self.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/solve", json={"time_limit_seconds": 15, "random_seed": 1}, headers=self.ctx.headers["administrator"]); self.assertEqual(solve.status_code, 201, solve.text); self.assertIn(solve.json()["status"], {"FEASIBLE", "OPTIMAL"})
        db = self.ctx.session_factory()
        try:
            events = list(db.scalars(select(CombinedTeachingEvent).where(CombinedTeachingEvent.combined_teaching_group_id == group_id))); self.assertEqual(len(events), 4)
            children = list(db.scalars(select(TimetableEntry).where(TimetableEntry.combined_teaching_event_id.is_not(None)))); self.assertEqual(len(children), 8)
            for event in events:
                siblings = [entry for entry in children if entry.combined_teaching_event_id == event.id]; self.assertEqual(len(siblings), 2); self.assertEqual({entry.section_id for entry in siblings}, {self.fixture.section.id, self.section_b.id}); self.assertEqual({entry.classroom_id for entry in siblings}, {self.large_room.id}); self.assertEqual({entry.faculty_id for entry in siblings}, {self.fixture.faculty.id})
            independent = list(db.scalars(select(TimetableEntry).where(TimetableEntry.course_offering_id == self.offering_c.id))); self.assertEqual(len(independent), 4)
            workload = {row.faculty_id: row.weekly_workload_hours for row in faculty_allocation_service.preview(db, faculty_id=None, academic_term_id=self.fixture.term.id, department_id=None)}
            # Shared theory is counted once (4); the same faculty also teaches
            # three physical laboratory-group occurrences (3 × 4).
            self.assertEqual(workload[self.fixture.faculty.id], 16); self.assertEqual(workload[self.faculty_c.id], 4)
            self.assertEqual(review_service.conflicts(db, self.fixture.version.id)["summary"]["total"], 0)
            administrator = db.scalar(select(User).where(User.email == "admin.test@vce.ac.in")); first = children[0]
            review_service.move(db, first, TimetableEntryMove(working_day_id=first.working_day_id, period_number=first.period_number, lock_after_move=False), administrator)
            siblings = list(db.scalars(select(TimetableEntry).where(TimetableEntry.combined_teaching_event_id == first.combined_teaching_event_id))); self.assertTrue(all(row.is_manual for row in siblings))
            review_service.lock(db, siblings[0], administrator, "Common class confirmed"); self.assertTrue(all(row.is_locked for row in siblings))
            review_service.unlock(db, siblings[0], administrator, "Review correction"); self.assertTrue(all(not row.is_locked for row in siblings))
            copied = review_service.copy_version(db, self.fixture.version.id, VersionCopyRequest(version_name="Combined Review Copy"), administrator)
            copied_events = list(db.scalars(select(CombinedTeachingEvent).where(CombinedTeachingEvent.timetable_version_id == copied.id))); self.assertEqual(len(copied_events), 4)
            copied_children = list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id == copied.id, TimetableEntry.combined_teaching_event_id.is_not(None)))); self.assertEqual(len(copied_children), 8); self.assertEqual(len({row.combined_teaching_event_id for row in copied_children}), 4)
            review_service.lock(db, copied_children[0], administrator, "Review common class")
            comparison = review_service.compare(db, copied.id, self.fixture.version.id); self.assertTrue(comparison["lock_state_changes"])
            self.assertEqual(comparison["lock_state_changes"][0]["to"]["common_class"], "DS-CSE-AB"); self.assertEqual(comparison["lock_state_changes"][0]["to"]["combined_sections"], "TST-A + TST-B")
        finally: db.close()
        faculty_grid = self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/views/faculty/{self.fixture.faculty.id}", headers=self.ctx.headers["administrator"]); self.assertEqual(faculty_grid.status_code, 200, faculty_grid.text)
        combined_rows = [entry for day in faculty_grid.json()["days"] for entry in day["entries"] if entry["combined_teaching_event_id"]]; self.assertEqual(len(combined_rows), 4); self.assertTrue(all(entry["combined_section_codes"] == ["TST-A", "TST-B"] for entry in combined_rows))
        classroom_grid = self.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/views/classroom/{self.large_room.id}", headers=self.ctx.headers["administrator"]); self.assertEqual(classroom_grid.status_code, 200)
        self.assertEqual(len([entry for day in classroom_grid.json()["days"] for entry in day["entries"] if entry["combined_teaching_event_id"]]), 4)


if __name__ == "__main__": unittest.main()
