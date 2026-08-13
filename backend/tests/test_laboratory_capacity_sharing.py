"""Focused regression tests for generic capacity-shared laboratory scheduling."""

import copy
import unittest
from collections import Counter
from uuid import uuid4

from pydantic import ValidationError

from app.modules.facilities.schemas import LaboratoryCreate
from app.modules.authentication.models import Permission, Role
from app.modules.facilities.models import Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.laboratory_batches.models import StudentBatch
from app.modules.timetables.solver_service import solver_service
from app.modules.timetables.models import TimetableEntry
from sqlalchemy import select
from tests import test_solver_input_builder as solver_support


class LaboratoryCapacitySharingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = solver_support.SolverInputBuilderTests("test_build_reuses_identical_snapshot_and_marks_ready")
        self.fixture.setUp()
        self.response = self.fixture.client.post(
            f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input",
            headers=self.fixture.ctx.headers["administrator"],
        )
        self.assertEqual(self.response.status_code, 201, self.response.text)
        db=self.fixture.ctx.session_factory()
        try:
            permissions=[Permission(resource="timetable_entries",action="manage"),Permission(resource="timetable_entries",action="move"),Permission(resource="timetable_views",action="read")];db.add_all(permissions);db.flush()
            administrator=db.scalar(select(Role).where(Role.name=="Administrator"));administrator.permissions.extend(permissions)
            laboratory=db.get(Laboratory,self.fixture.laboratory.id);laboratory.concurrent_usage_mode="CAPACITY_SHARED";laboratory.capacity=60
            batches=list(db.scalars(select(StudentBatch).where(StudentBatch.section_id==self.fixture.section.id).order_by(StudentBatch.sequence_number)))
            for batch in batches:batch.student_count=30
            self.batch_ids=[batch.id for batch in batches];self.allocation_ids=[]
            for index in range(3):
                faculty=Faculty(faculty_code=f"SHR{index+1:03d}",full_name=f"Shared Faculty {index+1}",department_id=self.fixture.ctx.active_department.id,designation="Assistant Professor",institutional_email=f"shared{index+1}@vce.ac.in",minimum_weekly_workload=0,maximum_weekly_workload=18)
                db.add(faculty);db.flush();allocation=LaboratoryFacultyAllocation(course_offering_id=self.fixture.lab_offering.id,faculty_id=faculty.id,role_type="MAIN");db.add(allocation);db.flush();self.allocation_ids.append(allocation.id)
            db.commit()
        finally:db.close()

    def tearDown(self):
        self.fixture.tearDown()

    def capacity_snapshot(self, demands, mode="CAPACITY_SHARED", capacity=60, same_faculty=False):
        source = self.response.json()["snapshot_json"]
        snapshot = copy.deepcopy(source)
        offering_template = next(item for item in source["course_offerings"] if item["course_type"] == "LABORATORY")
        allocation_template = next(item for item in source["laboratory_faculty_allocations"] if item["role_type"] == "MAIN")
        section_template = source["sections"][0]
        faculty_template = next(item for item in source["faculty"] if item["id"] == allocation_template["faculty_id"])
        laboratory = snapshot["laboratories"][0]
        laboratory.update({"capacity": capacity, "concurrent_usage_mode": mode, "availability_mode": "ALL_PERIODS"})
        day = snapshot["working_days"][0]

        sections=[];offerings=[];batches=[];allocations=[];faculty=[];profiles=[];slots=[];configs=[]
        common_faculty_id=str(uuid4())
        for index,demand in enumerate(demands,1):
            section_id=str(uuid4());offering_id=str(uuid4());batch_id=str(uuid4());faculty_id=common_faculty_id if same_faculty else str(uuid4())
            sections.append({**section_template,"id":section_id,"section_code":f"CAP-{index}","section_name":chr(64+index),"student_strength":demand})
            offerings.append({**offering_template,"id":offering_id,"section_id":section_id,"grouping_mode":"GROUPED","effective_group_count":1,"effective_lab_group_count":1,"sessions_per_week":1,"lab_sessions_per_week":1,"session_duration":2,"lab_session_duration":2,"effective_weekly_periods":2,"full_section_capacity_demand":demand,"eligible_laboratory_ids":[laboratory["id"]],"laboratory_selection_mode":"FIXED","fixed_laboratory_id":laboratory["id"]})
            batches.append({"id":batch_id,"section_id":section_id,"batch_name":f"{chr(64+index)}1","sequence_number":1,"roll_number_start":1,"roll_number_end":demand,"student_count":demand})
            allocations.append({**allocation_template,"id":str(uuid4()),"course_offering_id":offering_id,"faculty_id":faculty_id})
            if not any(item["id"]==faculty_id for item in faculty):faculty.append({**faculty_template,"id":faculty_id,"faculty_code":f"CAP{index:03d}"})
            profiles.append({"id":str(uuid4()),"resource_type":"FACULTY","resource_id":faculty_id,"academic_term_id":snapshot["metadata"]["academic_term_id"],"availability_mode":"ONLY_SELECTED"})
            for period in (1,2):slots.append({"id":str(uuid4()),"resource_type":"FACULTY","resource_id":faculty_id,"academic_term_id":snapshot["metadata"]["academic_term_id"],"working_day_id":day["id"],"period_number":period,"availability_type":"ALLOWED","reason":None})
            configs.append({"id":str(uuid4()),"course_offering_id":offering_id,"section_id":section_id,"number_of_groups":1,"group_naming_pattern":None,"is_rotation_enabled":False,"is_weekly_rotation":False})

        snapshot.update({"sections":sections,"course_offerings":offerings,"student_batches":batches,"laboratory_batch_configurations":configs,"laboratory_faculty_allocations":allocations,"laboratory_session_faculty_rules":[],"theory_faculty_allocations":[],"faculty":faculty,"faculty_availability":[],"faculty_scheduling_policies":[],"combined_teaching_groups":[],"laboratory_rotation_groups":[],"laboratory_rotation_blocks":[],"laboratory_rotation_assignments":[],"primary_classroom_assignments":[],"classrooms":[],"laboratories":[laboratory],"resource_availability_profiles":profiles,"resource_availability_slots":slots,"laboratory_availability_blocks":[],"working_days":[day],"locked_entries":[]})
        return snapshot

    def solve_snapshot(self, demands, mode="CAPACITY_SHARED", capacity=60, same_faculty=False):
        db=self.fixture.ctx.session_factory()
        try:return solver_service._solve_snapshot(db,self.capacity_snapshot(demands,mode,capacity,same_faculty),self.fixture.version.id,10,1)
        finally:db.close()

    def test_configuration_defaults_and_shared_capacity_validation(self):
        values={"laboratory_code":"ws-5a01","laboratory_name":"Engineering Workshop","room_number":"5a01","owning_department_id":uuid4()}
        exclusive=LaboratoryCreate(**values)
        self.assertEqual(exclusive.concurrent_usage_mode,"EXCLUSIVE");self.assertIsNone(exclusive.capacity)
        with self.assertRaises(ValidationError):LaboratoryCreate(**values,concurrent_usage_mode="CAPACITY_SHARED")
        shared=LaboratoryCreate(**values,concurrent_usage_mode="CAPACITY_SHARED",capacity=60)
        self.assertEqual((shared.concurrent_usage_mode,shared.capacity),("CAPACITY_SHARED",60))

    def test_solver_snapshot_and_hash_include_concurrency_configuration(self):
        first=self.response.json();laboratory=next(item for item in first["snapshot_json"]["laboratories"] if item["id"]==str(self.fixture.laboratory.id))
        self.assertEqual(laboratory["concurrent_usage_mode"],"EXCLUSIVE");self.assertIsNone(laboratory["capacity"])
        db=self.fixture.ctx.session_factory()
        try:
            record=db.get(Laboratory,self.fixture.laboratory.id);record.concurrent_usage_mode="CAPACITY_SHARED";record.capacity=60;db.commit()
        finally:db.close()
        changed=self.fixture.client.post(f"/api/v1/timetable-versions/{self.fixture.version.id}/build-solver-input",headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(changed.status_code,201,changed.text)
        updated=next(item for item in changed.json()["snapshot_json"]["laboratories"] if item["id"]==str(self.fixture.laboratory.id))
        self.assertEqual((updated["concurrent_usage_mode"],updated["capacity"]),("CAPACITY_SHARED",60));self.assertNotEqual(first["input_hash"],changed.json()["input_hash"])

    def test_exact_capacity_and_arbitrary_cumulative_occupancy(self):
        valid=self.solve_snapshot([30,30]);self.assertIn(valid["status"],{"FEASIBLE","OPTIMAL"});self.assertEqual(len(valid["entries"]),2)
        self.assertEqual({(str(item["laboratory_id"]),item["period_number"]) for item in valid["entries"]}, {(str(valid["entries"][0]["laboratory_id"]),1)})
        self.assertEqual(self.solve_snapshot([30,30,30])["status"],"INFEASIBLE")
        self.assertIn(self.solve_snapshot([31,29])["status"],{"FEASIBLE","OPTIMAL"})
        self.assertEqual(self.solve_snapshot([31,30])["status"],"INFEASIBLE")
        fallback=self.capacity_snapshot([30,30,30]);first=fallback["laboratories"][0];second={**first,"id":str(uuid4()),"laboratory_code":"WS-5A02","room_number":"5A02"};fallback["laboratories"].append(second)
        for offering in fallback["course_offerings"]:offering.update({"laboratory_selection_mode":"AUTO","fixed_laboratory_id":None,"eligible_laboratory_ids":[first["id"],second["id"]]})
        db=self.fixture.ctx.session_factory()
        try:alternative=solver_service._solve_snapshot(db,fallback,self.fixture.version.id,10,1)
        finally:db.close()
        self.assertIn(alternative["status"],{"FEASIBLE","OPTIMAL"});self.assertEqual(sorted(Counter(str(item["laboratory_id"]) for item in alternative["entries"]).values()),[1,2])

    def test_exclusive_and_nonfacility_hard_constraints_remain_unchanged(self):
        self.assertEqual(self.solve_snapshot([30,30],mode="EXCLUSIVE")["status"],"INFEASIBLE")
        self.assertEqual(self.solve_snapshot([30,30],same_faculty=True)["status"],"INFEASIBLE")

    def test_full_capacity_and_multi_period_demand_is_enforced_each_period(self):
        self.assertIn(self.solve_snapshot([60])["status"],{"FEASIBLE","OPTIMAL"})
        self.assertEqual(self.solve_snapshot([60,1])["status"],"INFEASIBLE")

    def test_independent_rotation_blocks_share_capacity_but_cannot_exceed_it(self):
        def rotation_snapshot(block_count):
            snapshot=self.capacity_snapshot([30] * (block_count * 2))
            workshop=snapshot["laboratories"][0];blocks=[];assignments=[]
            for block_index in range(block_count):
                first=block_index * 2;second=first + 1
                section_id=snapshot["course_offerings"][first]["section_id"]
                snapshot["course_offerings"][second]["section_id"]=section_id
                snapshot["student_batches"][second]["section_id"]=section_id
                partner={**workshop,"id":str(uuid4()),"laboratory_code":f"PARTNER-{block_index + 1}","room_number":f"P-{block_index + 1}","concurrent_usage_mode":"EXCLUSIVE"}
                snapshot["laboratories"].append(partner)
                group_id=str(uuid4());block_id=str(uuid4())
                blocks.append({"id":block_id,"rotation_group_id":group_id,"block_number":1,"block_name":f"Block {block_index + 1}"})
                for position,(item_index,laboratory_id) in enumerate(((first,workshop["id"]),(second,partner["id"])),1):
                    allocation=snapshot["laboratory_faculty_allocations"][item_index]
                    assignments.append({"id":str(uuid4()),"rotation_group_id":group_id,"rotation_block_id":block_id,"batch_id":snapshot["student_batches"][item_index]["id"],"course_offering_id":snapshot["course_offerings"][item_index]["id"],"laboratory_id":laboratory_id,"main_faculty_id":allocation["faculty_id"],"supporting_faculty_ids":[],"session_duration":2,"rotation_position":position})
            snapshot["laboratory_rotation_blocks"]=blocks;snapshot["laboratory_rotation_assignments"]=assignments
            return snapshot,workshop["id"]

        db=self.fixture.ctx.session_factory()
        try:
            exact,workshop_id=rotation_snapshot(2)
            result=solver_service._solve_snapshot(db,exact,self.fixture.version.id,10,1)
            self.assertIn(result["status"],{"FEASIBLE","OPTIMAL"})
            shared=[item for item in result["entries"] if str(item["laboratory_id"])==workshop_id]
            self.assertEqual(len(shared),2)
            self.assertEqual({(str(item["working_day_id"]),item["period_number"]) for item in shared},{(str(shared[0]["working_day_id"]),1)})
            exceeded,_=rotation_snapshot(3)
            self.assertEqual(solver_service._solve_snapshot(db,exceeded,self.fixture.version.id,10,1)["status"],"INFEASIBLE")
        finally:db.close()

    def test_manual_entries_use_remaining_capacity_and_free_query_reports_it(self):
        url=f"/api/v1/timetable-versions/{self.fixture.version.id}/entries"
        def payload(index):
            return {"course_offering_id":str(self.fixture.lab_offering.id),"section_id":str(self.fixture.section.id),"laboratory_faculty_allocation_id":str(self.allocation_ids[index]),"laboratory_id":str(self.fixture.laboratory.id),"student_batch_id":str(self.batch_ids[index]),"working_day_id":str(self.fixture.working_day.id),"period_number":5,"session_length":2,"entry_type":"LABORATORY","is_manual":True}
        first=self.fixture.client.post(url,json=payload(0),headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(first.status_code,201,first.text)
        free=self.fixture.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/free-laboratories?working_day_id={self.fixture.working_day.id}&period_number=5&student_batch_id={self.batch_ids[1]}",headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(free.status_code,200,free.text)
        available=next(item for item in free.json()["items"] if item["id"]==str(self.fixture.laboratory.id))
        self.assertEqual((available["capacity"],available["occupied"],available["available"]),(60,30,30))
        second=self.fixture.client.post(url,json=payload(1),headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(second.status_code,201,second.text)
        third=self.fixture.client.post(url,json=payload(2),headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(third.status_code,409,third.text);self.assertIn("capacity 60",third.json()["detail"]);self.assertIn("occupancy is 60",third.json()["detail"])
        elsewhere={**payload(2),"period_number":1}
        movable=self.fixture.client.post(url,json=elsewhere,headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(movable.status_code,201,movable.text)
        moved=self.fixture.client.post(f"/api/v1/timetable-entries/{movable.json()['id']}/move",json={"working_day_id":str(self.fixture.working_day.id),"period_number":5,"lock_after_move":False},headers=self.fixture.ctx.headers["administrator"])
        self.assertEqual(moved.status_code,409,moved.text);self.assertIn("capacity 60",moved.json()["detail"])
        free=self.fixture.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/free-laboratories?working_day_id={self.fixture.working_day.id}&period_number=5",headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(free.status_code,200,free.text)
        self.assertNotIn(str(self.fixture.laboratory.id),{item["id"] for item in free.json()["items"]})
        conflicts=self.fixture.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/conflicts",headers=self.fixture.ctx.headers["administrator"]);self.assertEqual(conflicts.status_code,200,conflicts.text);self.assertNotIn("RESOURCE_CAPACITY_EXCEEDED",{item["conflict_type"] for item in conflicts.json()["conflicts"]})
        db=self.fixture.ctx.session_factory()
        try:
            extra=TimetableEntry(timetable_version_id=self.fixture.version.id,course_offering_id=self.fixture.lab_offering.id,section_id=self.fixture.section.id,laboratory_faculty_allocation_id=self.allocation_ids[2],laboratory_id=self.fixture.laboratory.id,student_batch_id=self.batch_ids[2],working_day_id=self.fixture.working_day.id,period_number=5,session_length=2,entry_type="LABORATORY",is_manual=True,is_locked=False);db.add(extra);db.commit()
        finally:db.close()
        conflicts=self.fixture.client.get(f"/api/v1/timetable-versions/{self.fixture.version.id}/conflicts",headers=self.fixture.ctx.headers["administrator"]);self.assertIn("RESOURCE_CAPACITY_EXCEEDED",{item["conflict_type"] for item in conflicts.json()["conflicts"]})


if __name__ == "__main__":
    unittest.main()
