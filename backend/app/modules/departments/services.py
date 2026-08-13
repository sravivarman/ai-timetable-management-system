"""Department management use cases."""

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.departments.models import Department
from app.modules.departments.repositories import DepartmentRepository
from app.modules.departments.schemas import DepartmentCreate, DepartmentPage, DepartmentUpdate


class DepartmentService:
    def __init__(self) -> None:
        self.repository = DepartmentRepository()

    def list_departments(
        self, db: Session, *, search: str | None, include_inactive: bool, page: int, page_size: int
    ) -> DepartmentPage:
        items, total = self.repository.list(
            db,
            search=search,
            include_inactive=include_inactive,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return DepartmentPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )

    def get_department(self, db: Session, department_id: UUID) -> Department:
        department = self.repository.get(db, department_id)
        if department is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        return department

    def create_department(self, db: Session, payload: DepartmentCreate) -> Department:
        self._ensure_unique_code(db, payload.department_code)
        return self.repository.save(db, Department(**payload.model_dump()))

    def update_department(self, db: Session, department_id: UUID, payload: DepartmentUpdate) -> Department:
        department = self.get_department(db, department_id)
        changes = payload.model_dump(exclude_unset=True)
        if "department_code" in changes:
            self._ensure_unique_code(db, changes["department_code"], exclude_id=department.id)
        for field, value in changes.items():
            setattr(department, field, value)
        return self.repository.save(db, department)

    def soft_delete_department(self, db: Session, department_id: UUID) -> Department:
        department = self.get_department(db, department_id)
        department.is_active = False
        return self.repository.save(db, department)

    def restore_department(self, db: Session, department_id: UUID) -> Department:
        department = self.get_department(db, department_id)
        department.is_active = True
        return self.repository.save(db, department)

    def _ensure_unique_code(self, db: Session, department_code: str, exclude_id: UUID | None = None) -> None:
        existing = self.repository.get_by_code(db, department_code)
        if existing is not None and existing.id != exclude_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department code already exists")


department_service = DepartmentService()
