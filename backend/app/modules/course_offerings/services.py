"""Course offering business rules."""

from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.course_offerings.repositories import CourseOfferingRepository
from app.modules.course_offerings.schemas import CourseOfferingBulkCreate, CourseOfferingCreate, CourseOfferingPage, CourseOfferingUpdate
from app.modules.courses.models import Course
from app.modules.facilities.models import Laboratory
from app.modules.sections.models import Section


class CourseOfferingService:
    def __init__(self) -> None:
        self.repository = CourseOfferingRepository()

    def list_offerings(self, db: Session, *, search: str | None, page: int, page_size: int, **filters) -> CourseOfferingPage:
        items, total = self.repository.list(db, search=search, filters=filters, offset=(page - 1) * page_size, limit=page_size)
        return CourseOfferingPage(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

    def get_offering(self, db: Session, offering_id: UUID) -> CourseOffering:
        offering = self.repository.get(db, offering_id)
        if offering is None:
            raise HTTPException(404, "Course offering not found")
        return offering

    def create_offering(self, db: Session, payload: CourseOfferingCreate) -> CourseOffering:
        data = payload.model_dump()
        self._validate_references(db, data)
        self._ensure_unique(db, data["course_id"], data["section_id"], data["academic_term_id"])
        self._validate_deprecated_common_theory_compatibility(db, data)
        self._validate_laboratory_selection(db, data)
        return self.repository.save(db, CourseOffering(**data))

    def create_bulk(self, db: Session, payload: CourseOfferingBulkCreate) -> list[CourseOffering]:
        if len(set(payload.course_ids)) != len(payload.course_ids):
            raise HTTPException(409, "Bulk course IDs must be unique")
        bulk_data = payload.model_dump()
        if bulk_data["is_common_theory"] and len(payload.course_ids) > 1:
            raise HTTPException(422, "A common theory group can contain only one course")
        created: list[CourseOffering] = []
        try:
            for course_id in payload.course_ids:
                data = CourseOfferingCreate(course_id=course_id, section_id=payload.section_id, academic_term_id=payload.academic_term_id, is_mandatory=payload.is_mandatory, elective_group_name=payload.elective_group_name, common_theory_group_code=bulk_data["common_theory_group_code"], is_common_theory=bulk_data["is_common_theory"], laboratory_selection_mode=bulk_data["laboratory_selection_mode"], laboratory_override_id=bulk_data["laboratory_override_id"]).model_dump()
                self._validate_references(db, data)
                self._ensure_unique(db, data["course_id"], data["section_id"], data["academic_term_id"])
                self._validate_deprecated_common_theory_compatibility(db, data)
                self._validate_laboratory_selection(db, data)
                created.append(CourseOffering(**data))
            db.add_all(created)
            db.commit()
            for offering in created:
                db.refresh(offering)
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, "Course offering already exists") from error
        except Exception:
            db.rollback()
            raise
        return created

    def update_offering(self, db: Session, offering_id: UUID, payload: CourseOfferingUpdate) -> CourseOffering:
        offering = self.get_offering(db, offering_id)
        changes = payload.model_dump(exclude_unset=True)
        data = {column.name: getattr(offering, column.name) for column in CourseOffering.__table__.columns if column.name not in {"id", "is_active", "created_at", "updated_at"}}
        data.update(changes)
        self._validate_deprecated_common_theory_compatibility(db, data, exclude_id=offering.id)
        self._validate_laboratory_selection(db, data)
        for name, value in changes.items():
            setattr(offering, name, value)
        return self.repository.save(db, offering)

    def soft_delete_offering(self, db: Session, offering_id: UUID) -> CourseOffering:
        offering = self.get_offering(db, offering_id)
        offering.is_active = False
        return self.repository.save(db, offering)

    def restore_offering(self, db: Session, offering_id: UUID) -> CourseOffering:
        offering = self.get_offering(db, offering_id)
        self._validate_references(db, {"course_id": offering.course_id, "section_id": offering.section_id, "academic_term_id": offering.academic_term_id})
        self._ensure_unique(db, offering.course_id, offering.section_id, offering.academic_term_id, exclude_id=offering.id)
        self._validate_laboratory_selection(db, {column.name: getattr(offering, column.name) for column in CourseOffering.__table__.columns})
        offering.is_active = True
        return self.repository.save(db, offering)

    @staticmethod
    def _validate_references(db: Session, data: dict) -> None:
        course = db.scalar(select(Course).where(Course.id == data["course_id"]))
        section = db.scalar(select(Section).where(Section.id == data["section_id"]))
        term = db.scalar(select(AcademicTerm).where(AcademicTerm.id == data["academic_term_id"]))
        if course is None or not course.is_active:
            raise HTTPException(422, "Course must exist and be active")
        if section is None or not section.is_active:
            raise HTTPException(422, "Section must exist and be active")
        if term is None or not term.is_active:
            raise HTTPException(422, "Academic term must exist and be active")
        if section.academic_term_id != term.id:
            raise HTTPException(422, "Section academic term must match course offering academic term")

    def _ensure_unique(self, db: Session, course_id: UUID, section_id: UUID, term_id: UUID, exclude_id: UUID | None = None) -> None:
        if self.repository.get_duplicate(db, course_id, section_id, term_id, exclude_id):
            raise HTTPException(409, "Course is already offered to this section for the academic term")

    @staticmethod
    def _validate_deprecated_common_theory_compatibility(db: Session, data: dict, exclude_id: UUID | None = None) -> None:
        """Validate legacy API input only; this metadata never drives scheduling."""
        course = db.scalar(select(Course).where(Course.id == data["course_id"]))
        if data.get("is_common_theory"):
            if course is None or course.course_type != "THEORY":
                raise HTTPException(422, "Common theory is allowed only for THEORY courses")
            group_code = data.get("common_theory_group_code")
            if not group_code:
                raise HTTPException(422, "Common theory group code is required")
            query = select(CourseOffering).where(CourseOffering.is_common_theory.is_(True), CourseOffering.common_theory_group_code == group_code, CourseOffering.academic_term_id == data["academic_term_id"])
            if exclude_id:
                query = query.where(CourseOffering.id != exclude_id)
            matching = db.scalar(query)
            if matching is not None and matching.course_id != data["course_id"]:
                raise HTTPException(422, "Common theory group code must reference the same course in an academic term")
        elif data.get("common_theory_group_code"):
            raise HTTPException(422, "Common theory group code requires is_common_theory=true")

    @staticmethod
    def _validate_laboratory_selection(db: Session, data: dict) -> None:
        mode = data.get("laboratory_selection_mode") or "AUTO"
        laboratory_id = data.get("laboratory_override_id")
        if mode == "AUTO" and laboratory_id is not None:
            raise HTTPException(422, "AUTO laboratory selection cannot specify a laboratory")
        if mode in {"PREFERRED", "FIXED"} and laboratory_id is None:
            raise HTTPException(422, f"{mode} laboratory selection requires a laboratory")
        course = db.get(Course, data["course_id"])
        if not course:
            return
        if mode != "AUTO" and course.venue_requirement not in {"LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"}:
            raise HTTPException(422, "Laboratory selection is allowed only for laboratory-capable courses")
        if laboratory_id is None:
            return
        eligible_ids = set(course.eligible_laboratory_ids)
        # Backward compatibility for pre-migration ORM fixtures/rows.
        if course.default_laboratory_id:
            eligible_ids.add(course.default_laboratory_id)
        laboratory = db.get(Laboratory, laboratory_id)
        if not laboratory or not laboratory.is_active:
            raise HTTPException(422, "Offering laboratory must exist and be active")
        if laboratory_id not in eligible_ids:
            raise HTTPException(422, "Offering laboratory must be eligible for the course")
        if laboratory.owning_department_id != course.offering_department_id and not laboratory.is_shareable_across_departments:
            raise HTTPException(422, "Cross-department offering laboratory must be shareable")


course_offering_service = CourseOfferingService()
