"""Deterministic solver-input snapshot builder (no solving)."""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.combined_teaching.models import CombinedTeachingGroup, CombinedTeachingGroupMember
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.departments.models import Department
from app.modules.facilities.models import Classroom, Laboratory
from app.modules.facilities_constraints.models import LaboratoryAvailabilityBlock, SectionClassroomAssignment
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, LaboratorySessionFacultyRule, TheoryFacultyAllocation
from app.modules.faculty_scheduling.models import FacultyAvailability, FacultySchedulingPolicy
from app.modules.laboratory_batches.models import LaboratoryBatchConfiguration, LaboratoryRotationAssignment, LaboratoryRotationBlock, LaboratoryRotationGroup, StudentBatch
from app.modules.programs.models import Program
from app.modules.schedule_configuration.models import PeriodTiming, WorkingDay
from app.modules.resource_availability.models import ResourceAvailabilityProfile, ResourceAvailabilitySlot
from app.modules.resource_availability.service import availability_service
from app.modules.sections.models import Section
from app.modules.timetable_validation.models import ValidationRun
from app.modules.timetables.models import SolverInputSnapshot, Timetable, TimetableEntry, TimetableVersion


def canonical_value(value):
    if isinstance(value, UUID): return str(value)
    if isinstance(value, Enum): return value.value
    if isinstance(value, (datetime, date, time)): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, dict): return {str(k): canonical_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)): return [canonical_value(v) for v in value]
    if isinstance(value, set): return [canonical_value(v) for v in sorted(value, key=str)]
    return value


def canonical_hash(snapshot):
    canonical = canonical_value(snapshot)
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return data, hashlib.sha256(data.encode("utf-8")).hexdigest()


def row_dict(row, *fields):
    return {field: canonical_value(getattr(row, field)) for field in fields}


class SolverInputBuilder:
    def _eligible(self, db, version_id):
        version = db.scalar(select(TimetableVersion).where(TimetableVersion.id == version_id))
        if version is None: raise HTTPException(404, "Timetable version not found")
        timetable = db.scalar(select(Timetable).where(Timetable.id == version.timetable_id))
        if timetable is None: raise HTTPException(404, "Timetable not found")
        run = db.scalar(select(ValidationRun).where(ValidationRun.id == version.validation_run_id))
        if run is None: raise HTTPException(422, "Linked validation run does not exist")
        if run.status not in {"PASSED", "WARNING"}: raise HTTPException(422, "Linked validation run must have PASSED or WARNING status")
        if timetable.status == "ARCHIVED": raise HTTPException(409, "Archived timetable is inactive")
        if not version.is_active: raise HTTPException(409, "Timetable version is inactive")
        if version.is_locked: raise HTTPException(409, "Timetable version is locked")
        if run.academic_term_id != timetable.academic_term_id: raise HTTPException(422, "Validation run academic term does not match timetable")
        for field in ("scope_type", "department_id", "program_id", "section_id"):
            if getattr(run, field) != getattr(timetable, field): raise HTTPException(422, "Validation run scope does not match timetable")
        return version, timetable, run

    def _scope(self, db, timetable):
        programs_query = select(Program).where(Program.is_active.is_(True))
        if timetable.scope_type == "SECTION":
            section = db.scalar(select(Section).where(Section.id == timetable.section_id))
            programs_query = programs_query.where(Program.id == (section.program_id if section else None))
        elif timetable.scope_type == "PROGRAM":
            programs_query = programs_query.where(Program.id == timetable.program_id)
        elif timetable.scope_type == "DEPARTMENT":
            programs_query = programs_query.where(Program.department_id == timetable.department_id)
        programs = list(db.scalars(programs_query.order_by(Program.program_code, Program.id)))
        program_ids = {program.id for program in programs}
        department_ids = {program.department_id for program in programs}
        if timetable.scope_type == "COLLEGE":
            departments_query = select(Department).where(Department.is_active.is_(True))
        else:
            departments_query = select(Department).where(
                Department.id.in_(department_ids), Department.is_active.is_(True)
            )
        departments = list(db.scalars(departments_query.order_by(Department.department_code, Department.id)))
        active_department_ids = {department.id for department in departments}
        programs = [program for program in programs if program.department_id in active_department_ids]
        program_ids = {program.id for program in programs}
        sections_query = select(Section).where(
            Section.academic_term_id == timetable.academic_term_id,
            Section.program_id.in_(program_ids),
            Section.is_active.is_(True),
        )
        if timetable.scope_type == "SECTION":
            sections_query = sections_query.where(Section.id == timetable.section_id)
        sections = list(db.scalars(sections_query.order_by(Section.section_code, Section.id)))
        return departments, programs, sections

    def build(self, db, version_id, persist=True):
        version, timetable, run = self._eligible(db, version_id)
        academic_term = db.scalar(select(AcademicTerm).where(AcademicTerm.id == timetable.academic_term_id))
        departments, programs, sections = self._scope(db, timetable)
        section_ids = {x.id for x in sections}
        offerings = list(db.scalars(select(CourseOffering).where(CourseOffering.section_id.in_(section_ids), CourseOffering.academic_term_id == timetable.academic_term_id, CourseOffering.is_active.is_(True)).order_by(CourseOffering.section_id, CourseOffering.course_id, CourseOffering.id))) if section_ids else []
        offering_ids = {x.id for x in offerings}; course_ids = {x.course_id for x in offerings}
        courses = list(db.scalars(select(Course).where(Course.id.in_(course_ids), Course.is_active.is_(True)).order_by(Course.course_code, Course.id))) if course_ids else []
        course_by_id = {x.id: x for x in courses}; offerings = [x for x in offerings if x.course_id in course_by_id]
        section_by_id = {x.id: x for x in sections}
        offerings.sort(key=lambda x: (section_by_id[x.section_id].section_code, course_by_id[x.course_id].course_code, str(x.id)))
        offering_ids = {x.id for x in offerings}
        combined_members = list(db.scalars(select(CombinedTeachingGroupMember).join(CombinedTeachingGroup).where(CombinedTeachingGroupMember.course_offering_id.in_(offering_ids), CombinedTeachingGroupMember.is_active.is_(True), CombinedTeachingGroup.is_active.is_(True), CombinedTeachingGroup.academic_term_id == timetable.academic_term_id).order_by(CombinedTeachingGroupMember.combined_teaching_group_id, CombinedTeachingGroupMember.course_offering_id, CombinedTeachingGroupMember.id))) if offering_ids else []
        candidate_group_ids = {x.combined_teaching_group_id for x in combined_members}
        all_members = list(db.scalars(select(CombinedTeachingGroupMember).where(CombinedTeachingGroupMember.combined_teaching_group_id.in_(candidate_group_ids), CombinedTeachingGroupMember.is_active.is_(True)).order_by(CombinedTeachingGroupMember.combined_teaching_group_id, CombinedTeachingGroupMember.course_offering_id, CombinedTeachingGroupMember.id))) if candidate_group_ids else []
        members_by_group = {}
        for member in all_members: members_by_group.setdefault(member.combined_teaching_group_id, []).append(member)
        combined_groups = list(db.scalars(select(CombinedTeachingGroup).where(CombinedTeachingGroup.id.in_({group_id for group_id, members in members_by_group.items() if {x.course_offering_id for x in members} <= offering_ids}), CombinedTeachingGroup.is_active.is_(True)).order_by(CombinedTeachingGroup.group_code, CombinedTeachingGroup.id))) if members_by_group else []
        combined_group_ids = {x.id for x in combined_groups}
        combined_members = [x for x in all_members if x.combined_teaching_group_id in combined_group_ids]
        theory = list(db.scalars(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id.in_(offering_ids), TheoryFacultyAllocation.is_active.is_(True)).order_by(TheoryFacultyAllocation.course_offering_id, TheoryFacultyAllocation.faculty_id, TheoryFacultyAllocation.id))) if offering_ids else []
        lab_allocations = list(db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id.in_(offering_ids), LaboratoryFacultyAllocation.is_active.is_(True)).order_by(LaboratoryFacultyAllocation.course_offering_id, LaboratoryFacultyAllocation.role_type, LaboratoryFacultyAllocation.faculty_id, LaboratoryFacultyAllocation.id))) if offering_ids else []
        allocation_ids = {x.id for x in lab_allocations}; faculty_ids = {x.faculty_id for x in theory} | {x.faculty_id for x in lab_allocations} | {x.faculty_id for x in combined_groups}
        faculty = list(db.scalars(select(Faculty).where(Faculty.id.in_(faculty_ids), Faculty.is_active.is_(True)).order_by(Faculty.faculty_code, Faculty.id))) if faculty_ids else []
        faculty_ids = {x.id for x in faculty}
        availability = list(db.scalars(select(FacultyAvailability).where(FacultyAvailability.faculty_id.in_(faculty_ids), FacultyAvailability.academic_term_id == timetable.academic_term_id, FacultyAvailability.is_active.is_(True)).order_by(FacultyAvailability.faculty_id, FacultyAvailability.day_of_week, FacultyAvailability.period_number, FacultyAvailability.id))) if faculty_ids else []
        policies = list(db.scalars(select(FacultySchedulingPolicy).where(FacultySchedulingPolicy.faculty_id.in_(faculty_ids), FacultySchedulingPolicy.academic_term_id == timetable.academic_term_id, FacultySchedulingPolicy.is_active.is_(True)).order_by(FacultySchedulingPolicy.faculty_id, FacultySchedulingPolicy.id))) if faculty_ids else []
        rules = list(db.scalars(select(LaboratorySessionFacultyRule).where(LaboratorySessionFacultyRule.laboratory_faculty_allocation_id.in_(allocation_ids), LaboratorySessionFacultyRule.is_active.is_(True)).order_by(LaboratorySessionFacultyRule.laboratory_faculty_allocation_id, LaboratorySessionFacultyRule.session_number, LaboratorySessionFacultyRule.id))) if allocation_ids else []
        batches = list(db.scalars(select(StudentBatch).where(StudentBatch.section_id.in_(section_ids), StudentBatch.is_active.is_(True)).order_by(StudentBatch.section_id, StudentBatch.sequence_number, StudentBatch.id))) if section_ids else []
        configs = list(db.scalars(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id.in_(offering_ids), LaboratoryBatchConfiguration.is_active.is_(True)).order_by(LaboratoryBatchConfiguration.course_offering_id, LaboratoryBatchConfiguration.id))) if offering_ids else []
        config_by_offering = {configuration.course_offering_id: configuration for configuration in configs}
        groups = list(db.scalars(select(LaboratoryRotationGroup).where(LaboratoryRotationGroup.section_id.in_(section_ids), LaboratoryRotationGroup.academic_term_id == timetable.academic_term_id, LaboratoryRotationGroup.is_active.is_(True)).order_by(LaboratoryRotationGroup.rotation_code, LaboratoryRotationGroup.id))) if section_ids else []
        group_ids = {x.id for x in groups}
        rotation_blocks = list(db.scalars(select(LaboratoryRotationBlock).where(LaboratoryRotationBlock.rotation_group_id.in_(group_ids), LaboratoryRotationBlock.is_active.is_(True)).order_by(LaboratoryRotationBlock.rotation_group_id, LaboratoryRotationBlock.block_number, LaboratoryRotationBlock.id))) if group_ids else []
        rotation_block_ids = {x.id for x in rotation_blocks}
        assignments = list(db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.rotation_group_id.in_(group_ids), LaboratoryRotationAssignment.rotation_block_id.in_(rotation_block_ids), LaboratoryRotationAssignment.batch_id.in_({x.id for x in batches}), LaboratoryRotationAssignment.course_offering_id.in_(offering_ids), LaboratoryRotationAssignment.is_active.is_(True)).order_by(LaboratoryRotationAssignment.rotation_group_id, LaboratoryRotationAssignment.rotation_block_id, LaboratoryRotationAssignment.rotation_position, LaboratoryRotationAssignment.id))) if rotation_block_ids else []
        rotation_faculty_ids = {assignment.main_faculty_id for assignment in assignments if assignment.main_faculty_id} | {UUID(str(value)) for assignment in assignments for value in (assignment.supporting_faculty_ids or [])}
        all_faculty_ids = faculty_ids | rotation_faculty_ids
        faculty = list(db.scalars(select(Faculty).where(Faculty.id.in_(all_faculty_ids), Faculty.is_active.is_(True)).order_by(Faculty.faculty_code, Faculty.id))) if all_faculty_ids else []
        faculty_ids = {x.id for x in faculty}
        availability = list(db.scalars(select(FacultyAvailability).where(FacultyAvailability.faculty_id.in_(faculty_ids), FacultyAvailability.academic_term_id == timetable.academic_term_id, FacultyAvailability.is_active.is_(True)).order_by(FacultyAvailability.faculty_id, FacultyAvailability.day_of_week, FacultyAvailability.period_number, FacultyAvailability.id))) if faculty_ids else []
        policies = list(db.scalars(select(FacultySchedulingPolicy).where(FacultySchedulingPolicy.faculty_id.in_(faculty_ids), FacultySchedulingPolicy.academic_term_id == timetable.academic_term_id, FacultySchedulingPolicy.is_active.is_(True)).order_by(FacultySchedulingPolicy.faculty_id, FacultySchedulingPolicy.id))) if faculty_ids else []
        room_assignments = list(db.scalars(select(SectionClassroomAssignment).where(SectionClassroomAssignment.section_id.in_(section_ids), SectionClassroomAssignment.academic_term_id == timetable.academic_term_id, SectionClassroomAssignment.is_active.is_(True), SectionClassroomAssignment.is_primary.is_(True)).order_by(SectionClassroomAssignment.section_id, SectionClassroomAssignment.classroom_id, SectionClassroomAssignment.id))) if section_ids else []
        department_ids = {x.id for x in departments}
        classroom_ids = {x.classroom_id for x in room_assignments} | {x.preferred_classroom_id for x in combined_groups if x.preferred_classroom_id}
        classroom_scope = (Classroom.id.in_(classroom_ids)) | (Classroom.owning_department_id.in_(department_ids))
        classrooms = list(db.scalars(select(Classroom).where(classroom_scope, Classroom.is_active.is_(True)).order_by(Classroom.room_number, Classroom.id))) if classroom_ids or department_ids else []
        eligibility_links = list(db.scalars(select(CourseEligibleLaboratory).where(CourseEligibleLaboratory.course_id.in_(course_ids), CourseEligibleLaboratory.is_active.is_(True)).order_by(CourseEligibleLaboratory.course_id, CourseEligibleLaboratory.preference_priority, CourseEligibleLaboratory.laboratory_id))) if course_ids else []
        eligible_ids_by_course: dict[UUID, list[UUID]] = {}
        for link in eligibility_links:
            eligible_ids_by_course.setdefault(link.course_id, []).append(link.laboratory_id)
        # Pre-migration/default-only fixtures remain sensible, while explicit
        # eligibility is authoritative whenever it exists.
        for course in courses:
            if not eligible_ids_by_course.get(course.id) and course.default_laboratory_id:
                eligible_ids_by_course[course.id] = [course.default_laboratory_id]
        lab_ids = {laboratory_id for ids in eligible_ids_by_course.values() for laboratory_id in ids} | {offering.laboratory_override_id for offering in offerings if offering.laboratory_override_id} | {assignment.laboratory_id for assignment in assignments if assignment.laboratory_id} | {x.preferred_laboratory_id for x in combined_groups if x.preferred_laboratory_id}
        laboratory_scope = (Laboratory.id.in_(lab_ids)) | (Laboratory.owning_department_id.in_(department_ids))
        laboratories = list(db.scalars(select(Laboratory).where(laboratory_scope, Laboratory.is_active.is_(True)).order_by(Laboratory.laboratory_code, Laboratory.id))) if lab_ids or department_ids else []
        lab_ids = {x.id for x in laboratories}
        working_days = list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True), WorkingDay.is_working_day.is_(True)).order_by(WorkingDay.sequence_number, WorkingDay.id)))
        day_by_name = {x.day_name: x for x in working_days}
        resource_ids = {"FACULTY": faculty_ids, "CLASSROOM": {x.id for x in classrooms}, "LABORATORY": lab_ids}
        profiles=[]; generic_slots=[]
        for resource_type, ids in resource_ids.items():
            if not ids: continue
            stored=list(db.scalars(select(ResourceAvailabilityProfile).where(ResourceAvailabilityProfile.resource_type==resource_type,ResourceAvailabilityProfile.resource_id.in_(ids),ResourceAvailabilityProfile.academic_term_id==timetable.academic_term_id,ResourceAvailabilityProfile.is_active.is_(True)).order_by(ResourceAvailabilityProfile.resource_id,ResourceAvailabilityProfile.id)))
            stored_by_id={x.resource_id:x for x in stored};profiles.extend(row_dict(x,"id","resource_type","resource_id","academic_term_id","availability_mode") for x in stored)
            for resource_id in sorted(ids,key=str):
                if resource_id not in stored_by_id:
                    profiles.append({"id":None,"resource_type":resource_type,"resource_id":resource_id,"academic_term_id":timetable.academic_term_id,"availability_mode":availability_service.effective_mode(db,resource_type,resource_id,timetable.academic_term_id)})
            rows=list(db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.resource_type==resource_type,ResourceAvailabilitySlot.resource_id.in_(ids),ResourceAvailabilitySlot.academic_term_id==timetable.academic_term_id,ResourceAvailabilitySlot.is_active.is_(True)).order_by(ResourceAvailabilitySlot.resource_id,ResourceAvailabilitySlot.working_day_id,ResourceAvailabilitySlot.period_number,ResourceAvailabilitySlot.id)))
            generic_slots.extend(row_dict(x,"id","resource_type","resource_id","academic_term_id","working_day_id","period_number","availability_type","reason") for x in rows)
        # Legacy faculty records remain the source of soft preferences. Directly
        # inserted hard-unavailable rows are represented in generic snapshots too.
        existing_generic={(x["resource_id"],x["working_day_id"],x["period_number"]) for x in generic_slots if x["resource_type"]=="FACULTY"}
        for item in availability:
            day=day_by_name.get(item.day_of_week)
            if item.availability_type=="unavailable" and day and (item.faculty_id,day.id,item.period_number) not in existing_generic:
                generic_slots.append({"id":None,"resource_type":"FACULTY","resource_id":item.faculty_id,"academic_term_id":timetable.academic_term_id,"working_day_id":day.id,"period_number":item.period_number,"availability_type":"BLOCKED","reason":item.reason})
                for profile in profiles:
                    if profile["resource_type"]=="FACULTY" and profile["resource_id"]==item.faculty_id and profile["availability_mode"]=="ALL_PERIODS":profile["availability_mode"]="EXCEPT_BLOCKED"
        profiles.sort(key=lambda x:(x["resource_type"],str(x["resource_id"]),str(x.get("id") or "")))
        generic_slots.sort(key=lambda x:(x["resource_type"],str(x["resource_id"]),str(x["working_day_id"]),x["period_number"],str(x.get("id") or "")))
        lab_availability_blocks=[x for x in generic_slots if x["resource_type"]=="LABORATORY"]
        timings = list(db.scalars(select(PeriodTiming).where(PeriodTiming.is_active.is_(True)).order_by(PeriodTiming.schedule_type, PeriodTiming.sequence_number, PeriodTiming.id)))
        locked_entries = list(db.scalars(select(TimetableEntry).join(WorkingDay, WorkingDay.id == TimetableEntry.working_day_id).where(TimetableEntry.timetable_version_id == version.id, TimetableEntry.is_locked.is_(True)).order_by(WorkingDay.sequence_number, TimetableEntry.period_number, TimetableEntry.section_id, TimetableEntry.id)))
        def offering_snapshot(offering):
            course = course_by_id[offering.course_id]
            item = {
                **row_dict(offering,"id","course_id","section_id","academic_term_id","is_mandatory","elective_group_name"),
                "course_code": course.course_code,
                "course_name": course.course_name,
                "course_type": course.course_type,
                "grouping_mode": course.grouping_mode,
                "venue_requirement": course.venue_requirement,
                "effective_weekly_periods": offering.weekly_periods_override or course.weekly_periods,
                "elective_type": course.elective_type,
                "lab_session_duration": course.lab_session_duration,
                "lab_sessions_per_week": course.lab_sessions_per_week,
                "session_duration": course.lab_session_duration if course.course_type == "LABORATORY" and course.lab_session_duration else course.session_duration,
                "sessions_per_week": course.lab_sessions_per_week if course.course_type == "LABORATORY" and course.lab_sessions_per_week else course.sessions_per_week,
                "default_group_count": course.default_lab_group_count if course.course_type == "LABORATORY" and course.default_lab_group_count else course.default_group_count,
                "allows_same_course_double_period": course.allows_same_course_double_period,
                "default_laboratory_id": course.default_laboratory_id,
                "laboratory_selection_mode": offering.laboratory_selection_mode,
                "preferred_laboratory_id": offering.laboratory_override_id if offering.laboratory_selection_mode == "PREFERRED" else course.default_laboratory_id,
                "fixed_laboratory_id": offering.laboratory_override_id if offering.laboratory_selection_mode == "FIXED" else None,
            }
            configuration = config_by_offering.get(offering.id)
            item["effective_group_count"] = configuration.number_of_groups if configuration else course.default_group_count
            item["rotation_enabled"] = bool(configuration and configuration.is_rotation_enabled)
            item["eligible_classroom_ids"] = [
                classroom.id for classroom in classrooms
                if classroom.is_shareable or classroom.owning_department_id == course.offering_department_id
            ]
            allowed_ids = set(eligible_ids_by_course.get(course.id, []))
            item["eligible_laboratory_ids"] = [
                laboratory.id for laboratory in laboratories
                if laboratory.id in allowed_ids and (
                    laboratory.is_shareable_across_departments or laboratory.owning_department_id == course.offering_department_id
                )
            ]
            if offering.laboratory_selection_mode == "FIXED":
                item["eligible_laboratory_ids"] = [offering.laboratory_override_id] if offering.laboratory_override_id in item["eligible_laboratory_ids"] else []
            if course.course_type == "LABORATORY":
                item["course_default_lab_group_count"] = course.default_lab_group_count
                item["effective_lab_group_count"] = (
                    configuration.number_of_groups if configuration else course.default_lab_group_count
                )
            return item

        snapshot = {
            "metadata": {"timetable_id": timetable.id, "timetable_version_id": version.id, "academic_term_id": timetable.academic_term_id, "scope_type": timetable.scope_type, "department_id": timetable.department_id, "program_id": timetable.program_id, "section_id": timetable.section_id, "validation_run_id": run.id, "version_number": version.version_number,"year_number":academic_term.year_number if academic_term else None,"schedule_type":"FIRST_YEAR" if academic_term and academic_term.year_number==1 else "HIGHER_YEAR"},
            "departments": [row_dict(x,"id","department_code","department_name","short_name") for x in departments],
            "programs": [row_dict(x,"id","department_id","program_code","program_name","degree_type","duration_years") for x in programs],
            "sections": [row_dict(x,"id","program_id","academic_term_id","section_name","section_code","student_strength") for x in sections],
            "course_offerings": [offering_snapshot(x) for x in offerings],
            "theory_faculty_allocations":[row_dict(x,"id","course_offering_id","faculty_id") for x in theory if x.faculty_id in faculty_ids],
            "laboratory_faculty_allocations":[row_dict(x,"id","course_offering_id","faculty_id","role_type","required_with_main_faculty_id","alternative_group_code","minimum_sessions_per_week","maximum_sessions_per_week") for x in lab_allocations if x.faculty_id in faculty_ids],
            "laboratory_session_faculty_rules":[row_dict(x,"id","laboratory_faculty_allocation_id","session_number","is_mandatory_for_session") for x in rules],
            "faculty":[row_dict(x,"id","faculty_code","full_name","department_id","minimum_weekly_workload","maximum_weekly_workload","maximum_periods_per_day") for x in faculty],
            "faculty_availability":[row_dict(x,"id","faculty_id","day_of_week","period_number","availability_type","reason") for x in availability],
            "faculty_scheduling_policies":[row_dict(x,"id","faculty_id","maximum_periods_per_day","avoid_first_period","avoid_last_period","minimize_idle_gaps","fair_first_last_distribution","preferred_working_days") for x in policies],
            "student_batches":[row_dict(x,"id","section_id","batch_name","sequence_number","roll_number_start","roll_number_end","student_count") for x in batches],
            "laboratory_batch_configurations":[row_dict(x,"id","course_offering_id","section_id","number_of_groups","group_naming_pattern","is_rotation_enabled","is_weekly_rotation") for x in configs],
            "laboratory_rotation_groups":[row_dict(x,"id","laboratory_batch_configuration_id","section_id","academic_term_id","rotation_code","rotation_type") for x in groups],
            "laboratory_rotation_blocks":[row_dict(x,"id","rotation_group_id","block_number","block_name") for x in rotation_blocks],
            "laboratory_rotation_assignments":[row_dict(x,"id","rotation_group_id","rotation_block_id","batch_id","course_offering_id","laboratory_id","main_faculty_id","supporting_faculty_ids","session_duration","rotation_position") for x in assignments],
            "classrooms":[row_dict(x,"id","room_number","room_name","building_name","floor_number","capacity","owning_department_id","is_primary_classroom","is_shareable") for x in classrooms],
            "combined_teaching_groups":[{
                **row_dict(group,"id","academic_term_id","group_code","group_name","course_id","faculty_id","preferred_classroom_id","preferred_laboratory_id"),
                "course_offering_ids":[str(member.course_offering_id) for member in members_by_group[group.id]],
                "section_ids":[str(next(offering.section_id for offering in offerings if offering.id==member.course_offering_id)) for member in members_by_group[group.id]],
                "section_strengths":[section_by_id[next(offering.section_id for offering in offerings if offering.id==member.course_offering_id)].student_strength for member in members_by_group[group.id]],
                "combined_strength":sum(section_by_id[next(offering.section_id for offering in offerings if offering.id==member.course_offering_id)].student_strength for member in members_by_group[group.id]),
                "venue_requirement":course_by_id[group.course_id].venue_requirement,
                "eligible_classroom_ids":[str(group.preferred_classroom_id)] if group.preferred_classroom_id else [],
                "laboratory_selection_mode":"PREFERRED" if group.preferred_laboratory_id else "AUTO",
                "fixed_laboratory_id":None,
                "eligible_laboratory_ids":[str(laboratory.id) for laboratory in laboratories if laboratory.id in set(eligible_ids_by_course.get(group.course_id, [])) and (laboratory.is_shareable_across_departments or laboratory.owning_department_id==course_by_id[group.course_id].offering_department_id)],
                "weekly_periods":next(offering.weekly_periods_override or course_by_id[offering.course_id].weekly_periods for offering in offerings if offering.id==members_by_group[group.id][0].course_offering_id),
                "session_duration":course_by_id[group.course_id].session_duration,
                "sessions_per_week":course_by_id[group.course_id].sessions_per_week,
            } for group in combined_groups],
            "primary_classroom_assignments":[row_dict(x,"id","section_id","classroom_id","academic_term_id","effective_from","effective_to") for x in room_assignments],
            "laboratories":[row_dict(x,"id","laboratory_code","laboratory_name","room_number","owning_department_id","is_shareable_across_departments","is_available_all_periods","availability_mode") for x in laboratories],
            "resource_availability_profiles":profiles,
            "resource_availability_slots":generic_slots,
            "laboratory_availability_blocks":[{**x,"laboratory_id":x["resource_id"]} for x in lab_availability_blocks],
            "working_days":[row_dict(x,"id","day_name","sequence_number") for x in working_days],
            "period_timings":[row_dict(x,"id","schedule_type","period_number","start_time","end_time","duration_minutes","is_instructional","break_type","sequence_number") for x in timings],
            "locked_entries":[row_dict(x,"id","timetable_version_id","course_offering_id","section_id","faculty_id","laboratory_faculty_allocation_id","classroom_id","laboratory_id","student_batch_id","laboratory_rotation_block_id","laboratory_rotation_assignment_id","combined_teaching_event_id","working_day_id","period_number","session_length","entry_type","is_manual","is_locked") for x in locked_entries],
        }
        snapshot = canonical_value(snapshot); _, digest = canonical_hash(snapshot)
        if not persist:return digest
        existing = db.scalar(select(SolverInputSnapshot).where(SolverInputSnapshot.timetable_version_id == version.id, SolverInputSnapshot.input_hash == digest).order_by(SolverInputSnapshot.created_at.desc(), SolverInputSnapshot.id.desc()))
        if existing is not None:
            if version.solver_status != "READY": version.solver_status="READY"; db.commit()
            return existing
        created = SolverInputSnapshot(timetable_version_id=version.id,snapshot_json=snapshot,input_hash=digest,created_at=datetime.now(timezone.utc));version.solver_status="READY";db.add(created);db.commit();db.refresh(created);return created

    def latest(self, db, version_id):
        if db.scalar(select(TimetableVersion.id).where(TimetableVersion.id == version_id)) is None: raise HTTPException(404,"Timetable version not found")
        snapshot=db.scalar(select(SolverInputSnapshot).where(SolverInputSnapshot.timetable_version_id==version_id).order_by(SolverInputSnapshot.created_at.desc(),SolverInputSnapshot.id.desc()))
        if snapshot is None: raise HTTPException(404,"Solver input snapshot not found")
        return snapshot

    def current_hash(self,db,version_id):return self.build(db,version_id,persist=False)


solver_input_builder=SolverInputBuilder()
build_snapshot=solver_input_builder.build
