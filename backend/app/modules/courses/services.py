"""Course master use cases and business-rule validation."""

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.courses.repositories import CourseRepository
from app.modules.courses.schemas import CourseCreate, CoursePage, CourseUpdate
from app.modules.departments.models import Department
from app.modules.facilities.models import Laboratory


class CourseService:
    def __init__(self) -> None:
        self.repository = CourseRepository()

    def list_courses(self, db: Session, *, search: str | None, page: int, page_size: int, **filters) -> CoursePage:
        items, total = self.repository.list(db, search=search, filters=filters, offset=(page - 1) * page_size, limit=page_size)
        return CoursePage(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

    def get_course(self, db: Session, course_id: UUID) -> Course:
        course = self.repository.get(db, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        return course

    def create_course(self, db: Session, payload: CourseCreate) -> Course:
        data = payload.model_dump()
        eligible_ids = self._effective_requested_eligible_ids(data.pop("eligible_laboratory_ids", []), data.get("default_laboratory_id"), "eligible_laboratory_ids" not in payload.model_fields_set)
        self._normalize_schedule_data(data)
        self._ensure_active_department(db, data["offering_department_id"])
        self._ensure_unique_code(db, data["course_code"])
        self._validate_course_data(db, data, eligible_ids)
        course = Course(**data)
        try:
            db.add(course)
            db.flush()
            self._sync_eligible_laboratories(db, course, eligible_ids)
            db.commit()
            db.refresh(course)
            return course
        except Exception:
            db.rollback()
            raise

    def update_course(self, db: Session, course_id: UUID, payload: CourseUpdate) -> Course:
        course = self.get_course(db, course_id)
        changes = payload.model_dump(exclude_unset=True)
        requested_eligible_ids = changes.pop("eligible_laboratory_ids", None)
        if "session_duration" not in changes and "lab_session_duration" in changes:
            changes["session_duration"] = changes["lab_session_duration"]
        if "sessions_per_week" not in changes and "lab_sessions_per_week" in changes:
            changes["sessions_per_week"] = changes["lab_sessions_per_week"]
        if "default_group_count" not in changes and "default_lab_group_count" in changes:
            changes["default_group_count"] = changes["default_lab_group_count"]
        data = {column.name: getattr(course, column.name) for column in Course.__table__.columns if column.name not in {"id", "created_at", "updated_at", "is_active"}}
        data.update(changes)
        current_eligible_ids = [link.laboratory_id for link in course.eligible_laboratory_links if link.is_active]
        eligible_ids = self._effective_requested_eligible_ids(
            requested_eligible_ids if requested_eligible_ids is not None else current_eligible_ids,
            data.get("default_laboratory_id"),
            requested_eligible_ids is None,
        )
        if requested_eligible_ids is not None:
            from app.modules.course_offerings.models import CourseOffering, CourseOfferingAllowedLaboratory
            restricted_ids = set(db.scalars(
                select(CourseOfferingAllowedLaboratory.laboratory_id)
                .join(CourseOffering, CourseOffering.id == CourseOfferingAllowedLaboratory.course_offering_id)
                .where(
                    CourseOffering.course_id == course.id,
                    CourseOffering.laboratory_selection_mode == "RESTRICTED",
                    CourseOffering.is_active.is_(True),
                    CourseOfferingAllowedLaboratory.is_active.is_(True),
                )
            ))
            if not restricted_ids.issubset(set(eligible_ids)):
                raise HTTPException(status_code=422, detail="Course eligibility cannot remove a laboratory used by an active RESTRICTED offering")
        self._normalize_schedule_data(data)
        self._ensure_active_department(db, data["offering_department_id"])
        if "course_code" in changes:
            self._ensure_unique_code(db, data["course_code"], exclude_id=course.id)
        self._validate_course_data(db, data, eligible_ids)
        for name, value in changes.items():
            setattr(course, name, value)
        for name in ("grouping_mode", "venue_requirement", "session_duration", "sessions_per_week", "default_group_count"):
            setattr(course, name, data[name])
        if data["course_type"] == "LABORATORY":
            for name in ("lab_session_duration", "lab_sessions_per_week", "default_lab_group_count"):
                setattr(course, name, data[name])
        if "counts_toward_workload" not in changes:
            course.counts_toward_workload = data["counts_toward_workload"]
        try:
            db.add(course)
            self._sync_eligible_laboratories(db, course, eligible_ids)
            db.commit()
            db.refresh(course)
            return course
        except Exception:
            db.rollback()
            raise

    def soft_delete_course(self, db: Session, course_id: UUID) -> Course:
        course = self.get_course(db, course_id)
        course.is_active = False
        return self.repository.save(db, course)

    def restore_course(self, db: Session, course_id: UUID) -> Course:
        course = self.get_course(db, course_id)
        self._ensure_active_department(db, course.offering_department_id)
        course.is_active = True
        return self.repository.save(db, course)

    @staticmethod
    def _ensure_active_department(db: Session, department_id: UUID) -> None:
        department = db.scalar(select(Department).where(Department.id == department_id))
        if department is None or not department.is_active:
            raise HTTPException(status_code=422, detail="Offering department must exist and be active")

    def _ensure_unique_code(self, db: Session, code: str, exclude_id: UUID | None = None) -> None:
        existing = self.repository.get_by_code(db, code)
        if existing is not None and existing.id != exclude_id:
            raise HTTPException(status_code=409, detail="Course code already exists")

    @staticmethod
    def _validate_course_data(db: Session, data: dict, eligible_ids: list[UUID]) -> None:
        course_type = data["course_type"]
        if data["weekly_periods"] != data["session_duration"] * data["sessions_per_week"]:
            raise HTTPException(status_code=422, detail="Weekly periods must equal session duration multiplied by sessions per week")
        if data["grouping_mode"] == "FULL_SECTION" and data["default_group_count"] != 1:
            raise HTTPException(status_code=422, detail="FULL_SECTION courses must use a default group count of 1")
        if data["grouping_mode"] == "GROUPED" and data["default_group_count"] < 2:
            raise HTTPException(status_code=422, detail="GROUPED courses require at least two student groups")
        if data["venue_requirement"] == "LABORATORY_ONLY":
            if not eligible_ids:
                raise HTTPException(status_code=422, detail="LABORATORY_ONLY courses require at least one eligible laboratory")
        elif eligible_ids or data.get("default_laboratory_id") is not None:
            if data["venue_requirement"] != "CLASSROOM_OR_LABORATORY":
                raise HTTPException(status_code=422, detail="Laboratory eligibility is applicable only to laboratory-capable courses")
        laboratories = list(db.scalars(select(Laboratory).where(Laboratory.id.in_(eligible_ids)))) if eligible_ids else []
        if len(laboratories) != len(eligible_ids) or any(not laboratory.is_active for laboratory in laboratories):
            raise HTTPException(status_code=422, detail="Every eligible laboratory must exist and be active")
        for laboratory in laboratories:
            if laboratory.owning_department_id != data["offering_department_id"] and not laboratory.is_shareable_across_departments:
                raise HTTPException(status_code=422, detail="A cross-department eligible laboratory must be shareable")
        if data.get("default_laboratory_id") is not None and data["default_laboratory_id"] not in eligible_ids:
            raise HTTPException(status_code=422, detail="Preferred laboratory must be included in eligible laboratories")
        if data.get("counts_toward_workload") is None:
            data["counts_toward_workload"] = course_type not in {"LSM", "MINI_PROJECT", "PROJECT"}

    @staticmethod
    def _normalize_schedule_data(data: dict) -> None:
        """Populate generic scheduling fields and keep laboratory aliases in sync."""
        course_type = data["course_type"]
        duration = data.get("session_duration") or data.get("lab_session_duration") or 1
        sessions = data.get("sessions_per_week") or data.get("lab_sessions_per_week")
        if sessions is None:
            sessions = data["weekly_periods"] // duration if data["weekly_periods"] % duration == 0 else data["weekly_periods"]
        group_count = data.get("default_group_count") or data.get("default_lab_group_count") or 1
        data["session_duration"] = duration
        data["sessions_per_week"] = sessions
        data["default_group_count"] = group_count
        data["grouping_mode"] = data.get("grouping_mode") or ("GROUPED" if group_count > 1 else "FULL_SECTION")
        data["venue_requirement"] = data.get("venue_requirement") or (
            "LABORATORY_ONLY" if course_type == "LABORATORY" else
            "CLASSROOM_ONLY" if course_type in {"THEORY", "CDC"} else
            "CLASSROOM_OR_LABORATORY" if course_type == "PRACTICAL" else
            "NO_FIXED_VENUE"
        )
        if course_type == "LABORATORY":
            data["lab_session_duration"] = duration
            data["lab_sessions_per_week"] = sessions
            data["default_lab_group_count"] = group_count

    @staticmethod
    def _effective_requested_eligible_ids(values: list[UUID], preferred_id: UUID | None, allow_legacy_preferred_backfill: bool) -> list[UUID]:
        result = list(dict.fromkeys(values))
        # Backward-compatible clients may still submit only default_laboratory_id.
        if allow_legacy_preferred_backfill and preferred_id and preferred_id not in result:
            result.insert(0, preferred_id)
        return result

    @staticmethod
    def _sync_eligible_laboratories(db: Session, course: Course, laboratory_ids: list[UUID]) -> None:
        existing = {link.laboratory_id: link for link in course.eligible_laboratory_links}
        requested = set(laboratory_ids)
        for link in existing.values():
            link.is_active = link.laboratory_id in requested
        for priority, laboratory_id in enumerate(laboratory_ids, start=1):
            link = existing.get(laboratory_id)
            if link is None:
                link = CourseEligibleLaboratory(
                    course_id=course.id,
                    laboratory_id=laboratory_id,
                    preference_priority=priority,
                    is_active=True,
                )
                db.add(link)
                course.eligible_laboratory_links.append(link)
            else:
                link.preference_priority = priority
                link.is_active = True


course_service = CourseService()
