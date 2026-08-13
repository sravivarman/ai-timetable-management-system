"""Data access for Course master records."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.courses.models import Course


class CourseRepository:
    def get(self, db: Session, course_id: UUID) -> Course | None:
        return db.scalar(select(Course).where(Course.id == course_id))

    def get_by_code(self, db: Session, course_code: str) -> Course | None:
        return db.scalar(select(Course).where(Course.course_code == course_code))

    def list(self, db: Session, *, search: str | None, filters: dict, offset: int, limit: int) -> tuple[list[Course], int]:
        conditions = [getattr(Course, name) == value for name, value in filters.items() if value is not None]
        if search:
            term = f"%{search.strip()}%"
            conditions.append(or_(Course.course_code.ilike(term), Course.course_name.ilike(term)))
        statement = select(Course).where(*conditions).order_by(Course.course_code)
        total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        return list(db.scalars(statement.offset(offset).limit(limit))), total

    def save(self, db: Session, course: Course) -> Course:
        db.add(course)
        db.commit()
        db.refresh(course)
        return course
