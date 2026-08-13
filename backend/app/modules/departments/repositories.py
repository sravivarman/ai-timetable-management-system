"""SQLAlchemy repository for departments."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.departments.models import Department


class DepartmentRepository:
    def get(self, db: Session, department_id: UUID) -> Department | None:
        return db.scalar(select(Department).where(Department.id == department_id))

    def get_by_code(self, db: Session, department_code: str) -> Department | None:
        return db.scalar(select(Department).where(Department.department_code == department_code))

    def list(
        self,
        db: Session,
        *,
        search: str | None,
        include_inactive: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Department], int]:
        filters = []
        if not include_inactive:
            filters.append(Department.is_active.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Department.department_code.ilike(pattern),
                    Department.department_name.ilike(pattern),
                    Department.short_name.ilike(pattern),
                )
            )
        statement = select(Department).where(*filters).order_by(Department.department_code)
        total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        items = list(db.scalars(statement.offset(offset).limit(limit)))
        return items, total

    def save(self, db: Session, department: Department) -> Department:
        db.add(department)
        db.commit()
        db.refresh(department)
        return department
