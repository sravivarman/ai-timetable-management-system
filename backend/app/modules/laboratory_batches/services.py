from collections import Counter
from math import ceil
from string import Formatter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.facilities.models import Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.laboratory_batches.models import (
    LaboratoryBatchConfiguration,
    LaboratoryRotationAssignment,
    LaboratoryRotationBlock,
    LaboratoryRotationGroup,
    StudentBatch,
)
from app.modules.sections.models import Section


class Service:
    def get(self, db, model, record_id):
        record = db.scalar(select(model).where(model.id == record_id))
        if not record:
            raise HTTPException(404, "Record not found")
        return record

    def list(self, db, model, page=1, page_size=20, **filters):
        query = select(model)
        for key, value in filters.items():
            if value is not None and hasattr(model, key):
                query = query.where(getattr(model, key) == value)
        order = model.id
        if model is LaboratoryRotationGroup:
            order = LaboratoryRotationGroup.rotation_code
        elif model is LaboratoryRotationBlock:
            order = LaboratoryRotationBlock.block_number
        elif model is LaboratoryRotationAssignment:
            order = LaboratoryRotationAssignment.rotation_position
        query = query.order_by(order, model.id)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        return {"items": list(db.scalars(query.offset((page - 1) * page_size).limit(page_size))), "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    def save(self, db, record):
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def batches(self, db, section_id, count, overwrite=False, naming_pattern="{section}{sequence}"):
        section = self.get(db, Section, section_id)
        if not section.is_active:
            raise HTTPException(422, "Section must be active")
        if count < 1:
            raise HTTPException(422, "number_of_groups must be at least 1")
        if count > section.student_strength:
            raise HTTPException(422, "number_of_groups cannot exceed section student strength")
        names = self._group_names(section, naming_pattern, count)
        old = list(db.scalars(select(StudentBatch).where(StudentBatch.section_id == section_id, StudentBatch.is_active.is_(True))))
        if old and not overwrite:
            raise HTTPException(409, "Active student groups already exist for this section; use overwrite=true to replace them")
        try:
            for record in old:
                record.is_active = False
            if old:
                db.flush()
            base, extra = divmod(section.student_strength, count)
            output = []
            start = 1
            for sequence in range(1, count + 1):
                size = base + (1 if sequence <= extra else 0)
                output.append(StudentBatch(section_id=section_id, batch_name=names[sequence - 1], sequence_number=sequence, roll_number_start=start, roll_number_end=start + size - 1, student_count=size))
                start += size
            db.add_all(output)
            db.flush()
            db.commit()
            for record in output:
                db.refresh(record)
            return output
        except Exception:
            db.rollback()
            raise

    def config(self, db, data, record_id=None):
        current = self.get(db, LaboratoryBatchConfiguration, record_id) if record_id else None
        offering = self.get(db, CourseOffering, current.course_offering_id if current else data["course_offering_id"])
        course = self.get(db, Course, offering.course_id)
        if not offering.is_active or not course.is_active:
            raise HTTPException(422, "Only active course offerings are valid")
        if data.get("section_id", offering.section_id) != offering.section_id:
            raise HTTPException(422, "Configuration section must match offering section")
        section = self.get(db, Section, offering.section_id)
        count = data.get("number_of_groups", current.number_of_groups if current else None)
        if count is None or count < 1 or count > section.student_strength:
            raise HTTPException(422, "number_of_groups must be between 1 and the section student strength")
        if course.grouping_mode == "FULL_SECTION" and count != 1:
            raise HTTPException(422, "FULL_SECTION offerings must use one effective student group")
        if course.grouping_mode == "GROUPED" and count < 2:
            raise HTTPException(422, "GROUPED offerings require at least two student groups")
        pattern = data.get("group_naming_pattern", current.group_naming_pattern if current else "{section}{sequence}")
        self._group_names(section, pattern, count)
        existing = db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == offering.id, LaboratoryBatchConfiguration.is_active.is_(True)))
        if existing and (not current or existing.id != current.id):
            raise HTTPException(409, "Active configuration already exists")
        record = current or LaboratoryBatchConfiguration(**data)
        for key, value in data.items():
            setattr(record, key, value)
        return self.save(db, record)

    def create_rotation(self, db, data):
        anchor = self.get(db, LaboratoryBatchConfiguration, data["laboratory_batch_configuration_id"]) if data.get("laboratory_batch_configuration_id") else None
        section_id = data.get("section_id") or (anchor.section_id if anchor else None)
        if not section_id:
            raise HTTPException(422, "section_id or laboratory_batch_configuration_id is required")
        section = self.get(db, Section, section_id)
        offering = self.get(db, CourseOffering, anchor.course_offering_id) if anchor else None
        term_id = data.get("academic_term_id") or (offering.academic_term_id if offering else section.academic_term_id)
        if section.academic_term_id != term_id:
            raise HTTPException(422, "Rotation group academic term must match the section")
        values = dict(data, section_id=section_id, academic_term_id=term_id)
        return self.save(db, LaboratoryRotationGroup(**values))

    def generate_rotation(self, db, data):
        section = self.get(db, Section, data.section_id)
        term = self.get(db, AcademicTerm, data.academic_term_id)
        if not section.is_active or not term.is_active or section.academic_term_id != term.id:
            raise HTTPException(422, "Rotation requires an active section in the selected active academic term")
        offering_ids = list(dict.fromkeys(data.course_offering_ids))
        if len(offering_ids) < 2:
            raise HTTPException(422, "ROTATION_REQUIRES_MULTIPLE_LABS: at least two compatible multi-group activities are required")
        offerings = [self.get(db, CourseOffering, offering_id) for offering_id in offering_ids]
        courses = {offering.id: self.get(db, Course, offering.course_id) for offering in offerings}
        configurations = {offering.id: db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == offering.id, LaboratoryBatchConfiguration.is_active.is_(True))) for offering in offerings}
        for offering in offerings:
            course = courses[offering.id]
            if not offering.is_active or offering.section_id != section.id or offering.academic_term_id != term.id or course.course_type not in {"LABORATORY", "PRACTICAL"} or course.venue_requirement not in {"LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"} or not course.is_active:
                raise HTTPException(422, "All rotation offerings must be active laboratory-capable activities for the same section and academic term")
            if not configurations[offering.id]:
                raise HTTPException(422, "Every rotation offering requires an active student-group configuration")
            if configurations[offering.id].number_of_groups == 1:
                raise HTTPException(422, "ROTATION_SINGLE_GROUP_NOT_ALLOWED: full-section laboratories must be scheduled independently")
        counts = {configuration.number_of_groups for configuration in configurations.values()}
        if len(counts) != 1:
            raise HTTPException(422, "ROTATION_GROUP_CONFIGURATION_MISMATCH: rotating offerings must use the same student-group count")
        group_count = counts.pop()
        if len(offerings) < group_count:
            raise HTTPException(422, "ROTATION_INCOMPLETE: each parallel block needs a distinct laboratory offering for every student group")
        durations = {courses[offering.id].session_duration for offering in offerings}
        if None in durations or len(durations) != 1:
            raise HTTPException(422, "ROTATION_DURATION_MISMATCH: rotating laboratories must have the same session duration")
        session_counts = {courses[offering.id].sessions_per_week for offering in offerings}
        if None in session_counts or len(session_counts) != 1:
            raise HTTPException(422, "ROTATION_SESSION_PATTERN_MISMATCH: rotating activities must have the same sessions per week")
        sessions_per_week = session_counts.pop()
        active_groups = list(db.scalars(select(StudentBatch).where(StudentBatch.section_id == section.id, StudentBatch.is_active.is_(True)).order_by(StudentBatch.sequence_number, StudentBatch.id)))
        if data.student_group_ids:
            requested = set(data.student_group_ids)
            active_groups = [group for group in active_groups if group.id in requested]
        if len(active_groups) != group_count:
            raise HTTPException(422, "ROTATION_GROUP_CONFIGURATION_MISMATCH: selected active student groups must match the configured count")
        laboratories = {}
        main_faculty = {}
        for offering in offerings:
            course = courses[offering.id]
            fixed_id = offering.laboratory_override_id if offering.laboratory_selection_mode == "FIXED" else None
            laboratory = db.get(Laboratory, fixed_id) if fixed_id else None
            if course.course_type == "LABORATORY":
                main = db.scalar(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id == offering.id, LaboratoryFacultyAllocation.role_type == "MAIN", LaboratoryFacultyAllocation.is_active.is_(True)).order_by(LaboratoryFacultyAllocation.id))
            else:
                main = db.scalar(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id == offering.id, TheoryFacultyAllocation.is_active.is_(True)).order_by(TheoryFacultyAllocation.id))
            eligible_ids = set(course.eligible_laboratory_ids) or ({course.default_laboratory_id} if course.default_laboratory_id else set())
            if not eligible_ids or (laboratory and not laboratory.is_active) or not main:
                raise HTTPException(422, "Every rotation offering requires eligible laboratories and a MAIN faculty allocation")
            laboratories[offering.id] = laboratory
            main_faculty[offering.id] = main.faculty_id
        existing = db.scalar(select(LaboratoryRotationGroup).where(LaboratoryRotationGroup.section_id == section.id, LaboratoryRotationGroup.academic_term_id == term.id, LaboratoryRotationGroup.rotation_code == data.rotation_code, LaboratoryRotationGroup.is_active.is_(True)))
        if existing and not data.overwrite:
            raise HTTPException(409, "An active rotation group with this code already exists")
        try:
            if existing:
                self._deactivate_rotation(db, existing)
                db.flush()
            anchor = configurations[offerings[0].id]
            rotation = LaboratoryRotationGroup(laboratory_batch_configuration_id=anchor.id, section_id=section.id, academic_term_id=term.id, rotation_code=data.rotation_code.strip().upper(), rotation_type="CYCLIC")
            db.add(rotation)
            db.flush()
            for configuration in configurations.values():
                configuration.is_rotation_enabled = True
                configuration.is_weekly_rotation = False
            for block_index in range(len(offerings) * sessions_per_week):
                block = LaboratoryRotationBlock(rotation_group_id=rotation.id, block_number=block_index + 1, block_name=f"Block {block_index + 1}")
                db.add(block)
                db.flush()
                for group_index, student_group in enumerate(active_groups):
                    offering = offerings[(block_index + group_index) % len(offerings)]
                    db.add(LaboratoryRotationAssignment(rotation_group_id=rotation.id, rotation_block_id=block.id, batch_id=student_group.id, course_offering_id=offering.id, laboratory_id=laboratories[offering.id].id if laboratories[offering.id] else None, main_faculty_id=main_faculty[offering.id], supporting_faculty_ids=[], session_duration=courses[offering.id].session_duration, rotation_position=group_index + 1))
            db.flush()
            issues = self.rotation_issues(db, rotation)
            if issues:
                raise HTTPException(422, {"message": "Generated rotation is invalid", "issues": issues})
            db.commit()
            db.refresh(rotation)
            return self.matrix(db, rotation.id)
        except Exception:
            db.rollback()
            raise

    def matrix(self, db, group_id):
        group = self.get(db, LaboratoryRotationGroup, group_id)
        blocks = list(db.scalars(select(LaboratoryRotationBlock).where(LaboratoryRotationBlock.rotation_group_id == group.id, LaboratoryRotationBlock.is_active.is_(True)).order_by(LaboratoryRotationBlock.block_number, LaboratoryRotationBlock.id)))
        details = []
        student_group_ids = set()
        offering_ids = set()
        for block in blocks:
            assignments = list(db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.rotation_block_id == block.id, LaboratoryRotationAssignment.is_active.is_(True)).order_by(LaboratoryRotationAssignment.rotation_position, LaboratoryRotationAssignment.id)))
            student_group_ids.update(assignment.batch_id for assignment in assignments)
            offering_ids.update(assignment.course_offering_id for assignment in assignments)
            details.append({"id": block.id, "rotation_group_id": block.rotation_group_id, "block_number": block.block_number, "block_name": block.block_name, "is_active": block.is_active, "created_at": block.created_at, "updated_at": block.updated_at, "assignments": assignments})
        return {"group": group, "blocks": details, "student_group_ids": sorted(student_group_ids, key=str), "course_offering_ids": sorted(offering_ids, key=str)}

    def block(self, db, group_id, data, record_id=None):
        group = self.get(db, LaboratoryRotationGroup, group_id)
        record = self.get(db, LaboratoryRotationBlock, record_id) if record_id else LaboratoryRotationBlock(rotation_group_id=group.id, **data)
        if record.rotation_group_id != group.id:
            raise HTTPException(422, "Rotation block does not belong to the group")
        for key, value in data.items():
            setattr(record, key, value)
        return self.save(db, record)

    def assignment(self, db, group_id, data, record_id=None):
        group = self.get(db, LaboratoryRotationGroup, group_id)
        current = self.get(db, LaboratoryRotationAssignment, record_id) if record_id else None
        values = {
            key: getattr(current, key)
            for key in ("rotation_block_id", "batch_id", "course_offering_id", "laboratory_id", "main_faculty_id", "supporting_faculty_ids", "session_duration", "rotation_position")
        } if current else {}
        values.update(data)
        block = self.get(db, LaboratoryRotationBlock, values["rotation_block_id"])
        batch = self.get(db, StudentBatch, values["batch_id"])
        offering = self.get(db, CourseOffering, values["course_offering_id"])
        course = self.get(db, Course, offering.course_id)
        laboratory = self.get(db, Laboratory, values["laboratory_id"]) if values.get("laboratory_id") else None
        faculty_ids = [values["main_faculty_id"], *[UUID(str(value)) for value in values.get("supporting_faculty_ids") or []]]
        if block.rotation_group_id != group.id or batch.section_id != group.section_id or offering.section_id != group.section_id or offering.academic_term_id != group.academic_term_id:
            raise HTTPException(422, "Rotation assignment block, group, offering, and student group must share section and academic term")
        configuration = db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == offering.id, LaboratoryBatchConfiguration.is_active.is_(True)))
        if not batch.is_active or not offering.is_active or (laboratory and not laboratory.is_active) or not course.is_active or course.course_type not in {"LABORATORY", "PRACTICAL"} or course.venue_requirement not in {"LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"}:
            raise HTTPException(422, "Rotation assignments require active laboratory-capable activity resources")
        eligible_ids = set(course.eligible_laboratory_ids) or ({course.default_laboratory_id} if course.default_laboratory_id else set())
        if not eligible_ids or (laboratory and laboratory.id not in eligible_ids):
            raise HTTPException(422, "Rotation laboratory must be eligible for the course")
        if laboratory and laboratory.owning_department_id != course.offering_department_id and not laboratory.is_shareable_across_departments:
            raise HTTPException(422, "Cross-department rotation laboratory must be shareable")
        if offering.laboratory_selection_mode == "FIXED" and (not laboratory or laboratory.id != offering.laboratory_override_id):
            raise HTTPException(422, "FIXED offering rotation assignments must use the required laboratory")
        if not configuration or configuration.number_of_groups <= 1:
            raise HTTPException(422, "ROTATION_SINGLE_GROUP_NOT_ALLOWED: offering is not configured for rotation")
        if values["session_duration"] != course.session_duration:
            raise HTTPException(422, "ROTATION_DURATION_MISMATCH: assignment duration must match its laboratory course")
        if len(set(faculty_ids)) != len(faculty_ids) or any(not (faculty := db.get(Faculty, faculty_id)) or not faculty.is_active for faculty_id in faculty_ids):
            raise HTTPException(422, "Rotation faculty must be active and unique within the assignment")
        others = list(db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.rotation_block_id == block.id, LaboratoryRotationAssignment.is_active.is_(True), LaboratoryRotationAssignment.id != (current.id if current else None))))
        if any(other.batch_id == batch.id for other in others):
            raise HTTPException(409, "ROTATION_GROUP_DUPLICATE")
        if any(other.course_offering_id == offering.id or (laboratory and other.laboratory_id == laboratory.id) for other in others):
            raise HTTPException(409, "ROTATION_LAB_DUPLICATE")
        used_faculty = {faculty_id for other in others for faculty_id in [other.main_faculty_id, *(UUID(str(value)) for value in other.supporting_faculty_ids or [])] if faculty_id}
        if used_faculty.intersection(faculty_ids):
            raise HTTPException(409, "ROTATION_FACULTY_DUPLICATE")
        record = current or LaboratoryRotationAssignment(rotation_group_id=group.id, **values)
        for key, value in values.items():
            setattr(record, key, [str(item) for item in value] if key == "supporting_faculty_ids" else value)
        return self.save(db, record)

    def rotation_issues(self, db, group):
        blocks = list(db.scalars(select(LaboratoryRotationBlock).where(LaboratoryRotationBlock.rotation_group_id == group.id, LaboratoryRotationBlock.is_active.is_(True))))
        assignments = list(db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.rotation_group_id == group.id, LaboratoryRotationAssignment.is_active.is_(True))))
        offering_ids = {assignment.course_offering_id for assignment in assignments}
        batch_ids = {assignment.batch_id for assignment in assignments}
        issues = []
        def add(code, message):
            if not any(issue["issue_code"] == code for issue in issues):
                issues.append({"issue_code": code, "message": message})
        if len(offering_ids) < 2:
            add("ROTATION_REQUIRES_MULTIPLE_LABS", "A rotation requires at least two multi-group laboratory offerings")
        configs = {offering_id: db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id == offering_id, LaboratoryBatchConfiguration.is_active.is_(True))) for offering_id in offering_ids}
        offerings = {offering_id: db.get(CourseOffering, offering_id) for offering_id in offering_ids}
        courses = {offering_id: db.get(Course, offering.course_id) if offering else None for offering_id, offering in offerings.items()}
        batches = {batch_id: db.get(StudentBatch, batch_id) for batch_id in batch_ids}
        if any(
            not offering
            or not offering.is_active
            or offering.section_id != group.section_id
            or offering.academic_term_id != group.academic_term_id
            or not courses[offering_id]
            or not courses[offering_id].is_active
            or courses[offering_id].course_type not in {"LABORATORY", "PRACTICAL"}
            or courses[offering_id].venue_requirement not in {"LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"}
            for offering_id, offering in offerings.items()
        ) or any(not batch or not batch.is_active or batch.section_id != group.section_id for batch in batches.values()):
            add("ROTATION_GROUP_CONFIGURATION_MISMATCH", "Rotation resources must be active and share the group's section and academic term")
        if any(not config or config.number_of_groups == 1 for config in configs.values()):
            add("ROTATION_SINGLE_GROUP_NOT_ALLOWED", "Single-group laboratories must remain outside rotations")
        counts = {config.number_of_groups for config in configs.values() if config}
        if len(counts) != 1 or (counts and len(batch_ids) != next(iter(counts))):
            add("ROTATION_GROUP_CONFIGURATION_MISMATCH", "Rotation offerings and active student groups use different group counts")
        expected_groups = set(batch_ids)
        session_counts = {course.sessions_per_week for course in courses.values() if course}
        if len(session_counts) != 1:
            add("ROTATION_SESSION_PATTERN_MISMATCH", "Rotating activities must use the same sessions-per-week pattern")
        sessions_per_week = next(iter(session_counts), 0)
        expected_pairs = Counter({(batch_id, offering_id): sessions_per_week for batch_id in expected_groups for offering_id in offering_ids})
        actual_pairs = Counter((assignment.batch_id, assignment.course_offering_id) for assignment in assignments)
        if not blocks or actual_pairs != expected_pairs or len(blocks) != len(offering_ids) * sessions_per_week:
            add("ROTATION_INCOMPLETE", "Every student group must receive every activity for its configured sessions per week")
        for block in blocks:
            rows = [assignment for assignment in assignments if assignment.rotation_block_id == block.id]
            if len(rows) != len(expected_groups):
                add("ROTATION_INCOMPLETE", "Every block requires one assignment per student group")
            if len({row.batch_id for row in rows}) != len(rows):
                add("ROTATION_GROUP_DUPLICATE", "A student group appears more than once in a block")
            fixed_laboratories = [row.laboratory_id for row in rows if row.laboratory_id]
            if len({row.course_offering_id for row in rows}) != len(rows) or len(set(fixed_laboratories)) != len(fixed_laboratories):
                add("ROTATION_LAB_DUPLICATE", "A laboratory offering or room appears more than once in a block")
            faculty = [faculty_id for row in rows for faculty_id in [row.main_faculty_id, *(UUID(str(value)) for value in row.supporting_faculty_ids or [])] if faculty_id]
            if len(faculty) != len(set(faculty)):
                add("ROTATION_FACULTY_DUPLICATE", "A faculty member is assigned twice in the same parallel block")
            durations = {row.session_duration for row in rows}
            if None in durations or len(durations) != 1:
                add("ROTATION_DURATION_MISMATCH", "All assignments in a synchronized block require matching duration")
            for row in rows:
                course = courses.get(row.course_offering_id)
                if course and row.session_duration != course.session_duration:
                    add("ROTATION_DURATION_MISMATCH", "Assignment duration must match the laboratory course session duration")
        return issues

    def delete(self, db, model, record_id):
        record = self.get(db, model, record_id)
        record.is_active = False
        return self.save(db, record)

    def restore(self, db, model, record_id):
        record = self.get(db, model, record_id)
        record.is_active = True
        return self.save(db, record)

    def _deactivate_rotation(self, db, group):
        group.is_active = False
        blocks = list(db.scalars(select(LaboratoryRotationBlock).where(LaboratoryRotationBlock.rotation_group_id == group.id, LaboratoryRotationBlock.is_active.is_(True))))
        for block in blocks:
            block.is_active = False
        for assignment in db.scalars(select(LaboratoryRotationAssignment).where(LaboratoryRotationAssignment.rotation_group_id == group.id, LaboratoryRotationAssignment.is_active.is_(True))):
            assignment.is_active = False

    def _group_names(self, section, pattern, count):
        names = []
        try:
            fields = {field_name for _, field_name, _, _ in Formatter().parse(pattern) if field_name}
            if not fields.issubset({"section", "section_code", "sequence"}):
                raise ValueError
            for sequence in range(1, count + 1):
                name = pattern.format(section=section.section_name, section_code=section.section_code, sequence=sequence).strip().upper()
                if not name or len(name) > 20:
                    raise ValueError
                names.append(name)
        except (KeyError, ValueError, IndexError) as error:
            raise HTTPException(422, "Naming pattern must produce 1-20 character names using {section}, {section_code}, and/or {sequence}") from error
        if len(set(names)) != count:
            raise HTTPException(422, "Naming pattern must produce a unique name for every group")
        return names


service = Service()
