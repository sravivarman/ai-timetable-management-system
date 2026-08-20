"""Authoritative academic-session and Slot-workload calculations.

Academic sessions are coverage units, never raw periods or physical child rows.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.departments.models import Department
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation
from app.modules.laboratory_batches.models import LaboratoryRotationAssignment, StudentBatch
from app.modules.programs.models import Program
from app.modules.scheduling_slots.models import CourseOfferingSemesterRequirement, SchedulingSlot, SchedulingSlotWorkingDate, SlotCourseRequirement
from app.modules.sections.models import Section
from app.modules.timetables.models import Timetable, TimetableEntry, TimetableSessionProgressSnapshot, TimetableVersion


class SessionCountingService:
    def count_version(self, db, version_id: UUID) -> dict[UUID, int]:
        entries = list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id == version_id).order_by(TimetableEntry.course_offering_id, TimetableEntry.actual_date, TimetableEntry.working_day_id, TimetableEntry.period_number, TimetableEntry.id)))
        by_offering: dict[UUID, list[TimetableEntry]] = defaultdict(list)
        for entry in entries: by_offering[entry.course_offering_id].append(entry)
        result: dict[UUID, int] = {}
        for offering_id, rows in by_offering.items():
            # A physical occurrence is its actual date/day and starting period.
            # Combined children retain distinct Offering IDs and therefore add one
            # legitimate academic session to each participating Offering.
            def occurrence(row):
                return (row.actual_date or row.working_day_id, row.period_number, row.combined_teaching_event_id or row.laboratory_rotation_block_id)
            batch_ids = {row.student_batch_id for row in rows if row.student_batch_id}
            if not batch_ids:
                result[offering_id] = len({occurrence(row) for row in rows})
                continue
            section_id = rows[0].section_id
            expected = {item.id for item in db.scalars(select(StudentBatch).where(StudentBatch.section_id == section_id, StudentBatch.is_active.is_(True)))}
            expected = expected or batch_ids
            coverage = {batch_id: {occurrence(row) for row in rows if row.student_batch_id == batch_id} for batch_id in expected}
            # Every configured group must receive an occurrence before one
            # academic session is satisfied. This handles ordinary grouping and
            # complete cyclic rotations without multiplying by group count.
            result[offering_id] = min((len(values) for values in coverage.values()), default=0)
        return result

    def capture_workflow_snapshot(self, db, timetable: Timetable, version: TimetableVersion, status: str, created_at) -> None:
        counts = self.count_version(db, version.id)
        for offering_id, count in counts.items():
            existing = db.scalar(select(TimetableSessionProgressSnapshot).where(TimetableSessionProgressSnapshot.timetable_version_id == version.id, TimetableSessionProgressSnapshot.workflow_status == status, TimetableSessionProgressSnapshot.course_offering_id == offering_id))
            if existing is None:
                db.add(TimetableSessionProgressSnapshot(timetable_id=timetable.id, timetable_version_id=version.id, course_offering_id=offering_id, workflow_status=status, scheduled_sessions=count, created_at=created_at))

    def _latest_versions_by_slot(self, db, term_id, statuses=None, slot_id=None):
        query = select(TimetableVersion, Timetable).join(Timetable, Timetable.id == TimetableVersion.timetable_id).where(Timetable.academic_term_id == term_id, Timetable.scheduling_mode == "SLOT_BASED", TimetableVersion.scheduling_mode == "SLOT_BASED", TimetableVersion.is_active.is_(True))
        if slot_id: query = query.where(Timetable.scheduling_slot_id == slot_id)
        if statuses: query = query.where(Timetable.status.in_(statuses))
        rows = list(db.execute(query.order_by(Timetable.scheduling_slot_id, Timetable.updated_at.desc(), TimetableVersion.version_number.desc(), TimetableVersion.id.desc())))
        chosen = {}
        for version, timetable in rows: chosen.setdefault(timetable.scheduling_slot_id, (version, timetable))
        return chosen

    def progress_rows(self, db, term_id: UUID, slot_id: UUID | None = None, **filters):
        term = db.get(AcademicTerm, term_id)
        if not term: return []
        query = select(CourseOffering, Course, Section, Program, Department).join(Course, Course.id == CourseOffering.course_id).join(Section, Section.id == CourseOffering.section_id).join(Program, Program.id == Section.program_id).join(Department, Department.id == Program.department_id).where(CourseOffering.academic_term_id == term_id)
        for column, value in ((Department.id, filters.get("department_id")), (Program.id, filters.get("program_id")), (Section.id, filters.get("section_id")), (Course.id, filters.get("course_id")), (Course.course_type, filters.get("course_type"))):
            if value: query = query.where(column == value)
        contexts = list(db.execute(query.order_by(Department.department_code, Program.program_code, Section.section_code, Course.course_code, CourseOffering.id)))
        offering_ids = {row[0].id for row in contexts}
        semester = {row.course_offering_id: row for row in db.scalars(select(CourseOfferingSemesterRequirement).where(CourseOfferingSemesterRequirement.course_offering_id.in_(offering_ids), CourseOfferingSemesterRequirement.is_active.is_(True)))} if offering_ids else {}
        slot_query = select(SchedulingSlot).where(SchedulingSlot.academic_term_id == term_id, SchedulingSlot.is_active.is_(True))
        if slot_id: slot_query = slot_query.where(SchedulingSlot.id == slot_id)
        slots = list(db.scalars(slot_query.order_by(SchedulingSlot.sequence_number, SchedulingSlot.id)))
        slot_ids = {item.id for item in slots}; slot_by_id = {item.id: item for item in slots}
        reqs = list(db.scalars(select(SlotCourseRequirement).where(SlotCourseRequirement.scheduling_slot_id.in_(slot_ids), SlotCourseRequirement.course_offering_id.in_(offering_ids), SlotCourseRequirement.is_active.is_(True)))) if slot_ids and offering_ids else []
        req_by_key = {(row.scheduling_slot_id, row.course_offering_id): row.sessions_required for row in reqs}
        allocated = defaultdict(int)
        for row in reqs: allocated[row.course_offering_id] += row.sessions_required
        scheduled = defaultdict(int)
        for selected_slot, (version, _) in self._latest_versions_by_slot(db, term_id, slot_id=slot_id).items():
            for offering_id, count in self.count_version(db, version.id).items(): scheduled[(selected_slot, offering_id)] = count
        historical = defaultdict(int)
        snapshots = list(db.scalars(select(TimetableSessionProgressSnapshot).join(Timetable, Timetable.id == TimetableSessionProgressSnapshot.timetable_id).where(Timetable.academic_term_id == term_id, Timetable.scheduling_mode == "SLOT_BASED", TimetableSessionProgressSnapshot.course_offering_id.in_(offering_ids)).order_by(TimetableSessionProgressSnapshot.created_at.desc(), TimetableSessionProgressSnapshot.id.desc()))) if offering_ids else []
        seen = set()
        for item in snapshots:
            timetable = db.get(Timetable, item.timetable_id)
            key = (item.workflow_status, timetable.scheduling_slot_id, item.course_offering_id)
            if (not slot_id or timetable.scheduling_slot_id == slot_id) and key not in seen:
                historical[key] = item.scheduled_sessions; seen.add(key)
        rows = []
        for offering, course, section, program, department in contexts:
            target_slots = slots if slot_id else [None]
            for selected in target_slots:
                required = req_by_key.get((selected.id, offering.id)) if selected else allocated[offering.id]
                scheduled_count = scheduled.get((selected.id, offering.id), 0) if selected else sum(value for (sid, oid), value in scheduled.items() if oid == offering.id)
                approved = sum(value for (status, sid, oid), value in historical.items() if status == "APPROVED" and oid == offering.id and (selected is None or sid == selected.id))
                published = sum(value for (status, sid, oid), value in historical.items() if status == "PUBLISHED" and oid == offering.id and (selected is None or sid == selected.id))
                semester_row = semester.get(offering.id); planned = semester_row.total_sessions_required if semester_row else allocated[offering.id]
                reconciliation = self.reconcile(semester_row.total_sessions_required if semester_row else None, allocated[offering.id])
                progress_status = "COMPLETE" if scheduled_count >= required else "NOT_STARTED" if scheduled_count == 0 else "IN_PROGRESS"
                rows.append({"academic_year": term.academic_year, "academic_term": term.term_name, "department_code": department.department_code, "department_name": department.department_name, "program_code": program.program_code, "program_name": program.program_name, "section_code": section.section_code, "section_name": section.section_name, "course_code": course.course_code, "course_name": course.course_name, "course_type": course.course_type, "scheduling_slot_id": selected.id if selected else None, "slot_code": selected.slot_code if selected else None, "slot_name": selected.slot_name if selected else None, "sessions_required": required, **reconciliation, "scheduled_sessions": scheduled_count, "approved_sessions": approved, "published_sessions": published, "remaining_to_schedule": max(0, required - scheduled_count), "remaining_to_publish": max(0, planned - published), "progress_status": progress_status, "__academic_term_id": term.id, "__department_id": department.id, "__program_id": program.id, "__section_id": section.id, "__course_id": course.id, "__scheduling_slot_id": selected.id if selected else None, "__reconciliation_status": reconciliation["reconciliation_status"], "__progress_status": progress_status, "__stable_id": f"{selected.id if selected else 'semester'}:{offering.id}"})
        return rows

    @staticmethod
    def reconcile(required, allocated):
        from app.modules.scheduling_slots.service import scheduling_slot_service
        return scheduling_slot_service.reconcile(required, allocated)

    def slot_faculty_workload(self, db, term_id: UUID, slot_id: UUID):
        selected = self._latest_versions_by_slot(db, term_id, slot_id=slot_id).get(slot_id)
        if not selected: return []
        version, _ = selected; entries = list(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_version_id == version.id)))
        allocations = {item.id: item for item in db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.id.in_({entry.laboratory_faculty_allocation_id for entry in entries if entry.laboratory_faculty_allocation_id})))} if entries else {}
        rotation = {item.id: item for item in db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.id.in_({entry.laboratory_rotation_assignment_id for entry in entries if entry.laboratory_rotation_assignment_id})))} if entries else {}
        theory_periods=defaultdict(set); activity_periods=defaultdict(set); main_periods=defaultdict(set); supporting_periods=defaultdict(set); theory_sessions=defaultdict(set); activity_sessions=defaultdict(set)
        for entry in entries:
            faculty_roles=[]
            if entry.faculty_id: faculty_roles.append((entry.faculty_id,"MAIN"))
            allocation=allocations.get(entry.laboratory_faculty_allocation_id)
            if allocation: faculty_roles.append((allocation.faculty_id,allocation.role_type))
            assignment=rotation.get(entry.laboratory_rotation_assignment_id)
            if assignment:
                if assignment.main_faculty_id: faculty_roles.append((assignment.main_faculty_id,"MAIN"))
                faculty_roles.extend((UUID(value),"SUPPORTING") for value in assignment.supporting_faculty_ids or [])
            day=entry.actual_date or entry.working_day_id; occurrence=(day,entry.period_number,entry.combined_teaching_event_id or entry.laboratory_rotation_block_id or entry.id)
            for faculty_id,role in faculty_roles:
                target=theory_periods if entry.entry_type in {"THEORY","CDC"} else activity_periods
                sessions=theory_sessions if entry.entry_type in {"THEORY","CDC"} else activity_sessions
                sessions[faculty_id].add(occurrence)
                for period in range(entry.period_number,entry.period_number+entry.session_length):
                    key=(day,period);target[faculty_id].add(key);(main_periods if role=="MAIN" else supporting_periods)[faculty_id].add(key)
        slot=db.get(SchedulingSlot,slot_id);date_count=int(db.scalar(select(func.count()).select_from(SchedulingSlotWorkingDate).where(SchedulingSlotWorkingDate.scheduling_slot_id==slot_id,SchedulingSlotWorkingDate.is_active.is_(True))) or 0)
        departments={item.id:item for item in db.scalars(select(Department))};rows=[]
        faculty_ids=set(theory_periods)|set(activity_periods)
        for faculty_id in faculty_ids:
            member=db.get(Faculty,faculty_id);department=departments.get(member.department_id);per_day=defaultdict(int)
            for day,_ in theory_periods[faculty_id]|activity_periods[faculty_id]:per_day[day]+=1
            total=len(theory_periods[faculty_id]|activity_periods[faculty_id])
            rows.append({"academic_year":db.get(AcademicTerm,term_id).academic_year,"academic_term":db.get(AcademicTerm,term_id).term_name,"slot_code":slot.slot_code,"slot_name":slot.slot_name,"faculty_code":member.faculty_code,"faculty_name":member.full_name,"faculty_department":department.department_name if department else None,"designation":member.designation,"theory_sessions":len(theory_sessions[faculty_id]),"theory_periods":len(theory_periods[faculty_id]),"activity_sessions":len(activity_sessions[faculty_id]),"activity_periods":len(activity_periods[faculty_id]),"total_periods":total,"main_activity_periods":len(main_periods[faculty_id]),"supporting_activity_periods":len(supporting_periods[faculty_id]),"minimum_weekly_workload":member.minimum_weekly_workload,"maximum_weekly_workload":member.maximum_weekly_workload,"slot_working_date_count":date_count,"average_periods_per_working_date":round(total/date_count,2) if date_count else 0,"maximum_periods_on_any_slot_date":max(per_day.values(),default=0),"__academic_term_id":term_id,"__scheduling_slot_id":slot_id,"__faculty_id":faculty_id,"__department_id":member.department_id,"__stable_id":f"{slot_id}:{faculty_id}"})
        return sorted(rows,key=lambda row:(row["faculty_code"],row["__stable_id"]))


session_counting_service = SessionCountingService()
