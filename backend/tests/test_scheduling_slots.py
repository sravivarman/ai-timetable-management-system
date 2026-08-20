"""Generic Scheduling Slot API, demand, snapshot, and solver regressions."""

import copy
import os
import unittest
from datetime import date
from uuid import UUID

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission, Role, User
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.programs.models import Program
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.scheduling_slots.models import SchedulingSlot, SchedulingSlotWorkingDate, SlotCourseRequirement
from app.modules.scheduling_slots.models import CourseOfferingSemesterRequirement
from app.modules.scheduling_slots.progress import session_counting_service
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.timetables.models import TimetableEntry
from app.modules.resource_availability.service import availability_service
from app.modules.resource_availability.schemas import ResourceDateExceptionCreate
from app.modules.facilities.models import Classroom
from app.modules.sections.models import Section
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.demand import SlotDemandBuilder, WeeklyDemandBuilder
from app.modules.timetables.models import Timetable, TimetableVersion
from app.modules.timetables.service import solver_input_builder
from app.modules.timetables.solver_service import solver_service
from tests.facilities_test_support import create_facilities_test_context
from tests import test_solver_input_builder as solver_support
from tests import test_laboratory_rotation_engine as rotation_support


class SchedulingSlotEndpointTests(unittest.TestCase):
    def setUp(self):
        self.ctx = create_facilities_test_context()
        db = self.ctx.session_factory()
        try:
            permissions = [Permission(resource=resource, action=action) for resource, action in (
                ("scheduling_slots", "read"), ("scheduling_slots", "manage"),
                ("slot_requirements", "read"), ("slot_requirements", "manage"),
                ("semester_requirements", "read"), ("semester_requirements", "manage"),
                ("timetables", "read"), ("timetables", "manage"),
            )]
            db.add_all(permissions); db.flush()
            roles = {role.name: role for role in db.scalars(select(Role))}
            roles["Administrator"].permissions.extend(permissions)
            roles["Timetable Coordinator"].permissions.extend(permissions)
            roles["HOD"].permissions.extend([permissions[0], permissions[2], permissions[4], permissions[6]])
            self.term = AcademicTerm(academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 12, 31), is_active=True)
            db.add(self.term); db.flush()
            program = Program(department_id=self.ctx.active_department.id, program_code="TST-UG", program_name="Test UG")
            db.add(program); db.flush()
            self.section = Section(program_id=program.id, academic_term_id=self.term.id, section_name="A", section_code="TST-A", student_strength=60)
            course = Course(course_code="TST101", course_name="Slot Theory", offering_department_id=self.ctx.active_department.id, course_type="THEORY", weekly_periods=4, session_duration=1, sessions_per_week=4, default_group_count=1)
            db.add_all([self.section, course]); db.flush()
            self.offering = CourseOffering(course_id=course.id, section_id=self.section.id, academic_term_id=self.term.id)
            db.add(self.offering)
            db.add_all([WorkingDay(day_name=name, sequence_number=index) for index, name in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"), 1)])
            db.commit()
        finally:
            db.close()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.ctx.close()

    def create_slot(self, code="S01", sequence=1, start="2026-07-01", end="2026-07-31", role="administrator"):
        return self.client.post("/api/v1/scheduling-slots", headers=self.ctx.headers[role], json={"academic_term_id": str(self.term.id), "slot_code": code, "slot_name": f"Slot {sequence}", "sequence_number": sequence, "start_date": start, "end_date": end})

    def test_arbitrary_slot_count_ordering_uniqueness_and_permissions(self):
        for sequence in range(16, 0, -1):
            response = self.create_slot(f"X{sequence:02d}", sequence)
            self.assertEqual(response.status_code, 201, response.text)
        listing = self.client.get(f"/api/v1/scheduling-slots?academic_term_id={self.term.id}&page_size=100", headers=self.ctx.headers["hod"])
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()["total"], 16)
        self.assertEqual([item["sequence_number"] for item in listing.json()["items"]], list(range(1, 17)))
        self.assertEqual(self.create_slot("x01", 50).status_code, 409)
        self.assertEqual(self.create_slot("UNQ", 1).status_code, 409)
        self.assertEqual(self.create_slot("HOD", 30, role="hod").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/scheduling-slots", headers=self.ctx.headers["unauthorized"]).status_code, 403)

    def test_working_dates_are_actual_variable_and_non_overlapping(self):
        first = self.create_slot("S01", 1, "2026-07-06", "2026-07-20").json()
        second = self.create_slot("S02", 2, "2026-07-06", "2026-07-20").json()
        dates = ["2026-07-06", "2026-07-07", "2026-07-13"]
        saved = self.client.post(f"/api/v1/scheduling-slots/{first['id']}/working-dates", headers=self.ctx.headers["administrator"], json={"working_dates": dates, "replace": True})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual([item["working_date"] for item in saved.json()], dates)
        overlap = self.client.post(f"/api/v1/scheduling-slots/{second['id']}/working-dates", headers=self.ctx.headers["administrator"], json={"working_dates": [dates[0]], "replace": True})
        self.assertEqual(overlap.status_code, 409, overlap.text)
        sunday = self.client.post(f"/api/v1/scheduling-slots/{second['id']}/working-dates", headers=self.ctx.headers["administrator"], json={"working_dates": ["2026-07-12"], "replace": True})
        self.assertEqual(sunday.status_code, 422, sunday.text)

    def test_requirement_matrix_distinguishes_missing_zero_and_positive(self):
        first = self.create_slot("S01", 1).json(); second = self.create_slot("S02", 2).json()
        matrix = self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}", headers=self.ctx.headers["administrator"])
        self.assertEqual(matrix.status_code, 200, matrix.text)
        self.assertEqual([cell["status"] for cell in matrix.json()["rows"][0]["cells"]], ["MISSING", "MISSING"])
        bulk = self.client.post("/api/v1/slot-course-requirements/bulk", headers=self.ctx.headers["administrator"], json={"cells": [
            {"scheduling_slot_id": first["id"], "course_offering_id": str(self.offering.id), "sessions_required": 0},
            {"scheduling_slot_id": second["id"], "course_offering_id": str(self.offering.id), "sessions_required": 5},
        ]})
        self.assertEqual(bulk.status_code, 200, bulk.text)
        matrix = self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}&section_id={self.section.id}", headers=self.ctx.headers["administrator"]).json()
        self.assertEqual([cell["status"] for cell in matrix["rows"][0]["cells"]], ["CONFIGURED_ZERO", "CONFIGURED"])
        self.assertTrue(all(item["is_complete"] for item in matrix["completeness"]))
        duplicate = self.client.post("/api/v1/slot-course-requirements/bulk", headers=self.ctx.headers["administrator"], json={"cells": [
            {"scheduling_slot_id": first["id"], "course_offering_id": str(self.offering.id), "sessions_required": 1},
            {"scheduling_slot_id": first["id"], "course_offering_id": str(self.offering.id), "sessions_required": 2},
        ]})
        self.assertEqual(duplicate.status_code, 422, duplicate.text)
        db = self.ctx.session_factory()
        try:
            self.assertEqual(db.scalar(select(SlotCourseRequirement.sessions_required).where(SlotCourseRequirement.scheduling_slot_id == UUID(first["id"]))), 0)
        finally:
            db.close()

    def test_timetable_and_validation_mode_contracts(self):
        slot = self.create_slot().json()
        weekly_with_slot = self.client.post("/api/v1/timetables", headers=self.ctx.headers["administrator"], json={"academic_term_id": str(self.term.id), "scope_type": "COLLEGE", "scheduling_mode": "WEEKLY", "scheduling_slot_id": slot["id"], "name": "Invalid"})
        self.assertEqual(weekly_with_slot.status_code, 422)
        slot_without_id = self.client.post("/api/v1/timetables", headers=self.ctx.headers["administrator"], json={"academic_term_id": str(self.term.id), "scope_type": "COLLEGE", "scheduling_mode": "SLOT_BASED", "name": "Invalid"})
        self.assertEqual(slot_without_id.status_code, 422)
        valid = self.client.post("/api/v1/timetables", headers=self.ctx.headers["administrator"], json={"academic_term_id": str(self.term.id), "scope_type": "COLLEGE", "scheduling_mode": "SLOT_BASED", "scheduling_slot_id": slot["id"], "name": "Slot plan"})
        self.assertEqual(valid.status_code, 201, valid.text)
        self.assertEqual(valid.json()["scheduling_mode"], "SLOT_BASED")

    def test_semester_requirements_preserve_missing_zero_and_reconcile_slot_totals(self):
        first=self.create_slot("S01",1).json();second=self.create_slot("S02",2).json()
        matrix=self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}",headers=self.ctx.headers["administrator"]).json()
        self.assertIsNone(matrix["rows"][0]["semester_required"]);self.assertEqual(matrix["rows"][0]["reconciliation_status"],"NOT_CONFIGURED")
        created=self.client.post("/api/v1/semester-session-requirements",headers=self.ctx.headers["administrator"],json={"academic_term_id":str(self.term.id),"course_offering_id":str(self.offering.id),"total_sessions_required":0})
        self.assertEqual(created.status_code,201,created.text)
        matrix=self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}",headers=self.ctx.headers["administrator"]).json()["rows"][0]
        self.assertEqual((matrix["semester_required"],matrix["allocated_to_slots"],matrix["reconciliation_status"]),(0,0,"FULLY_ALLOCATED"))
        over=self.client.post("/api/v1/slot-course-requirements/bulk",headers=self.ctx.headers["administrator"],json={"cells":[{"scheduling_slot_id":first["id"],"course_offering_id":str(self.offering.id),"sessions_required":3}]})
        self.assertEqual(over.status_code,200,over.text);self.assertEqual(over.json()["warnings"][0]["code"],"SEMESTER_OVER_ALLOCATED")
        self.client.put(f"/api/v1/semester-session-requirements/{created.json()['id']}",headers=self.ctx.headers["administrator"],json={"total_sessions_required":5})
        row=self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}",headers=self.ctx.headers["administrator"]).json()["rows"][0]
        self.assertEqual((row["allocated_to_slots"],row["remaining_to_allocate"],row["reconciliation_status"]),(3,2,"UNDER_ALLOCATED"))
        self.client.post("/api/v1/slot-course-requirements/bulk",headers=self.ctx.headers["administrator"],json={"cells":[{"scheduling_slot_id":second["id"],"course_offering_id":str(self.offering.id),"sessions_required":2}]})
        row=self.client.get(f"/api/v1/slot-course-requirements/matrix?academic_term_id={self.term.id}",headers=self.ctx.headers["administrator"]).json()["rows"][0]
        self.assertEqual((row["allocated_to_slots"],row["remaining_to_allocate"],row["reconciliation_status"]),(5,0,"FULLY_ALLOCATED"))
        self.assertEqual(self.client.get(f"/api/v1/semester-session-requirements?academic_term_id={self.term.id}",headers=self.ctx.headers["hod"]).status_code,200)
        self.assertEqual(self.client.post("/api/v1/semester-session-requirements",headers=self.ctx.headers["hod"],json={"academic_term_id":str(self.term.id),"course_offering_id":str(self.offering.id),"total_sessions_required":1}).status_code,403)

    def test_date_specific_exception_overrides_only_its_calendar_date(self):
        db=self.ctx.session_factory()
        try:
            room=Classroom(room_number="SLOT-ROOM",room_name="Slot Room");day=db.scalar(select(WorkingDay).where(WorkingDay.day_name=="Monday"));db.add(room);db.commit()
            exception=availability_service.create_date_exception(db,ResourceDateExceptionCreate(resource_type="CLASSROOM",resource_id=room.id,academic_term_id=self.term.id,exception_date=date(2026,7,6),period_start=1,period_end=3,availability_status="UNAVAILABLE",reason="Maintenance"))
            self.assertFalse(availability_service.is_available(db,"CLASSROOM",room.id,self.term.id,day.id,2,date(2026,7,6)))
            self.assertTrue(availability_service.is_available(db,"CLASSROOM",room.id,self.term.id,day.id,2,date(2026,7,13)))
            self.assertEqual(exception.reason,"Maintenance")
        finally:db.close()

    def test_authoritative_session_counter_counts_sessions_and_group_coverage(self):
        db=self.ctx.session_factory()
        try:
            slot=SchedulingSlot(academic_term_id=self.term.id,slot_code="COUNT",slot_name="Count",sequence_number=50,start_date=date(2026,7,1),end_date=date(2026,7,31));db.add(slot);db.flush();user=db.scalar(select(User).where(User.username=="test-administrator"));day=db.scalar(select(WorkingDay).where(WorkingDay.day_name=="Monday"))
            run=ValidationRun(academic_term_id=self.term.id,scope_type="SECTION",section_id=self.section.id,scheduling_mode="SLOT_BASED",scheduling_slot_id=slot.id,status="PASSED",total_checks=1,passed_checks=1,failed_checks=0,warning_checks=0,created_by=user.id)
            timetable=Timetable(academic_term_id=self.term.id,scope_type="SECTION",section_id=self.section.id,scheduling_mode="SLOT_BASED",scheduling_slot_id=slot.id,name="Counter",created_by=user.id);db.add_all([run,timetable]);db.flush()
            version=TimetableVersion(timetable_id=timetable.id,version_number=1,source_type="GENERATED",validation_run_id=run.id,scheduling_mode="SLOT_BASED",scheduling_slot_id=slot.id,created_by=user.id);db.add(version);db.flush()
            db.add_all([TimetableEntry(timetable_version_id=version.id,course_offering_id=self.offering.id,section_id=self.section.id,working_day_id=day.id,actual_date=value,period_number=1,session_length=3,entry_type="THEORY") for value in (date(2026,7,6),date(2026,7,13))]);db.commit()
            self.assertEqual(session_counting_service.count_version(db,version.id)[self.offering.id],2)
            batches=[StudentBatch(section_id=self.section.id,batch_name=f"A{i}",sequence_number=i,roll_number_start=(i-1)*30+1,roll_number_end=i*30,student_count=30) for i in (1,2)];db.add_all(batches);db.flush()
            grouped=TimetableVersion(timetable_id=timetable.id,version_number=2,source_type="GENERATED",validation_run_id=run.id,scheduling_mode="SLOT_BASED",scheduling_slot_id=slot.id,created_by=user.id);db.add(grouped);db.flush()
            db.add_all([TimetableEntry(timetable_version_id=grouped.id,course_offering_id=self.offering.id,section_id=self.section.id,student_batch_id=batch.id,working_day_id=day.id,actual_date=date(2026,7,20),period_number=1,session_length=3,entry_type="LABORATORY") for batch in batches]);db.commit()
            self.assertEqual(session_counting_service.count_version(db,grouped.id)[self.offering.id],1)
            incomplete=TimetableVersion(timetable_id=timetable.id,version_number=3,source_type="GENERATED",validation_run_id=run.id,scheduling_mode="SLOT_BASED",scheduling_slot_id=slot.id,created_by=user.id);db.add(incomplete);db.flush();db.add(TimetableEntry(timetable_version_id=incomplete.id,course_offering_id=self.offering.id,section_id=self.section.id,student_batch_id=batches[0].id,working_day_id=day.id,actual_date=date(2026,7,27),period_number=1,session_length=3,entry_type="LABORATORY"));db.commit()
            self.assertEqual(session_counting_service.count_version(db,incomplete.id)[self.offering.id],0)
        finally:db.close()

    def test_mode_specific_demand_builders_preserve_weekly_semantics(self):
        offering = {"course_code": "TST101", "sessions_per_week": 4, "slot_sessions_required": 2}
        self.assertEqual(WeeklyDemandBuilder.sessions(offering), 4)
        self.assertEqual(SlotDemandBuilder.sessions(offering), 2)
        self.assertEqual(SlotDemandBuilder.sessions(offering | {"slot_sessions_required": 0}), 0)
        with self.assertRaisesRegex(ValueError, "Missing Slot Session Requirement"):
            SlotDemandBuilder.sessions(offering | {"slot_sessions_required": None})


class SlotSolverDateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready")
        self.fixture.setUp(); self.ctx = self.fixture.ctx

    def tearDown(self):
        self.fixture.tearDown()

    def test_snapshot_hash_and_solver_use_actual_dates(self):
        db = self.ctx.session_factory()
        try:
            slot = SchedulingSlot(academic_term_id=self.fixture.term.id, slot_code="S01", slot_name="Two Mondays", sequence_number=1, start_date=date(2026, 7, 6), end_date=date(2026, 7, 13))
            db.add(slot); db.flush()
            db.add_all([SchedulingSlotWorkingDate(scheduling_slot_id=slot.id, working_date=value) for value in (date(2026, 7, 6), date(2026, 7, 13))])
            db.add_all([SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.theory_offering.id, sessions_required=2), SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.lab_offering.id, sessions_required=0)])
            for record in (db.get(Timetable, self.fixture.timetable.id), db.get(TimetableVersion, self.fixture.version.id), db.get(ValidationRun, self.fixture.run.id)):
                record.scheduling_mode = "SLOT_BASED"; record.scheduling_slot_id = slot.id
            db.commit(); slot_id = slot.id
            first = solver_input_builder.build(db, self.fixture.version.id)
            same = solver_input_builder.build(db, self.fixture.version.id)
            self.assertEqual(first.id, same.id)
            self.assertEqual(first.input_hash, same.input_hash)
            snapshot = copy.deepcopy(first.snapshot_json)
            self.assertEqual(snapshot["metadata"]["scheduling_mode"], "SLOT_BASED")
            self.assertEqual(snapshot["metadata"]["scheduling_slot_id"], str(slot_id))
            self.assertEqual([item["actual_date"] for item in snapshot["scheduling_days"]], ["2026-07-06", "2026-07-13"])
            faculty_id = snapshot["theory_faculty_allocations"][0]["faculty_id"]
            snapshot["faculty_availability"] = [{"faculty_id": faculty_id, "day_of_week": day["day_name"], "period_number": period, "availability_type": "unavailable"} for day in snapshot["working_days"] for period in range(1, 8) if day["day_name"] != "Monday" or period != 1]
            result = solver_service._solve_snapshot(db, snapshot, self.fixture.version.id, 10, 1)
            self.assertIn(result["status"], {"FEASIBLE", "OPTIMAL"})
            theory = [item for item in result["entries"] if item["course_offering_id"] == self.fixture.theory_offering.id]
            self.assertEqual(len(theory), 2)
            self.assertEqual(len({item["actual_date"] for item in theory}), 2)
            requirement = db.scalar(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id == slot_id, SlotCourseRequirement.course_offering_id == self.fixture.theory_offering.id))
            requirement.sessions_required = 1; db.commit()
            changed = solver_input_builder.build(db, self.fixture.version.id)
            self.assertNotEqual(first.input_hash, changed.input_hash)
        finally:
            db.close()


class SlotRotationSolverTests(unittest.TestCase):
    def setUp(self):
        self.rotation = rotation_support.LaboratoryRotationEngineTests("test_two_groups_two_laboratories_swap")
        self.rotation.setUp(); self.ctx = self.rotation.ctx; self.fixture = self.rotation.fixture

    def tearDown(self):
        self.rotation.tearDown()

    def test_one_slot_session_runs_one_complete_rotation_cycle(self):
        self.rotation._set_group_count(2)
        second_offering_id = self.rotation._add_lab("SLOT", 2)
        self.rotation._generate([self.fixture.lab_offering.id, second_offering_id], "SLOT-CYCLE")
        db = self.ctx.session_factory()
        try:
            slot = SchedulingSlot(academic_term_id=self.fixture.term.id, slot_code="ROT", slot_name="Rotation Slot", sequence_number=1, start_date=date(2026, 7, 6), end_date=date(2026, 7, 9))
            db.add(slot); db.flush()
            db.add_all([SchedulingSlotWorkingDate(scheduling_slot_id=slot.id, working_date=value) for value in (date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8), date(2026, 7, 9))])
            db.add_all([
                SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.theory_offering.id, sessions_required=0),
                SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.lab_offering.id, sessions_required=1),
                SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=second_offering_id, sessions_required=1),
            ])
            for record in (db.get(Timetable, self.fixture.timetable.id), db.get(TimetableVersion, self.fixture.version.id), db.get(ValidationRun, self.fixture.run.id)):
                record.scheduling_mode = "SLOT_BASED"; record.scheduling_slot_id = slot.id
            db.commit()
            snapshot = solver_input_builder.build(db, self.fixture.version.id).snapshot_json
            result = solver_service._solve_snapshot(db, snapshot, self.fixture.version.id, 10, 11)
            self.assertIn(result["status"], {"FEASIBLE", "OPTIMAL"}, result)
            rotation_entries = [item for item in result["entries"] if item.get("laboratory_rotation_block_id")]
            self.assertEqual(len(rotation_entries), 4)
            pairs = {(item["student_batch_id"], item["course_offering_id"]) for item in rotation_entries}
            self.assertEqual(len(pairs), 4)
            self.assertTrue(all(item["actual_date"] is not None for item in rotation_entries))
        finally:
            db.close()

    def test_grouped_laboratory_demand_uses_sessions_per_group_on_actual_dates(self):
        db = self.ctx.session_factory()
        try:
            slot = SchedulingSlot(academic_term_id=self.fixture.term.id, slot_code="LAB", slot_name="Laboratory Slot", sequence_number=1, start_date=date(2026, 7, 6), end_date=date(2026, 7, 8))
            db.add(slot); db.flush()
            db.add_all([SchedulingSlotWorkingDate(scheduling_slot_id=slot.id, working_date=value) for value in (date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8))])
            db.add_all([
                SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.theory_offering.id, sessions_required=0),
                SlotCourseRequirement(scheduling_slot_id=slot.id, course_offering_id=self.fixture.lab_offering.id, sessions_required=1),
            ])
            for record in (db.get(Timetable, self.fixture.timetable.id), db.get(TimetableVersion, self.fixture.version.id), db.get(ValidationRun, self.fixture.run.id)):
                record.scheduling_mode = "SLOT_BASED"; record.scheduling_slot_id = slot.id
            db.commit()
            snapshot = solver_input_builder.build(db, self.fixture.version.id).snapshot_json
            result = solver_service._solve_snapshot(db, snapshot, self.fixture.version.id, 10, 7)
            self.assertIn(result["status"], {"FEASIBLE", "OPTIMAL"}, result)
            laboratory_entries = [item for item in result["entries"] if item["course_offering_id"] == self.fixture.lab_offering.id]
            self.assertEqual(len(laboratory_entries), 3)  # one academic session for each configured student group
            self.assertTrue(all(item["session_length"] == 2 for item in laboratory_entries))
            self.assertTrue(all(item["actual_date"] is not None for item in laboratory_entries))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
