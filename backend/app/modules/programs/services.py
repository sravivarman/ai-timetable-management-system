"""Program management use cases."""

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.programs.repositories import ProgramRepository
from app.modules.programs.schemas import ProgramCreate, ProgramPage, ProgramUpdate


class ProgramService:
    def __init__(self) -> None:
        self.repository = ProgramRepository()

    def list_programs(
        self,
        db: Session,
        *,
        search: str | None,
        department_id: UUID | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> ProgramPage:
        items, total = self.repository.list(
            db,
            search=search,
            department_id=department_id,
            include_inactive=include_inactive,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return ProgramPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )

    def get_program(self, db: Session, program_id: UUID) -> Program:
        program = self.repository.get(db, program_id)
        if program is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        return program

    def create_program(self, db: Session, payload: ProgramCreate) -> Program:
        self._ensure_active_department(db, payload.department_id)
        self._ensure_unique_code(db, payload.program_code)
        return self.repository.save(db, Program(**payload.model_dump()))

    def update_program(self, db: Session, program_id: UUID, payload: ProgramUpdate) -> Program:
        program = self.get_program(db, program_id)
        changes = payload.model_dump(exclude_unset=True)
        target_department_id = changes.get("department_id", program.department_id)
        self._ensure_active_department(db, target_department_id)
        if "program_code" in changes:
            self._ensure_unique_code(db, changes["program_code"], exclude_id=program.id)
        for field, value in changes.items():
            setattr(program, field, value)
        return self.repository.save(db, program)

    def soft_delete_program(self, db: Session, program_id: UUID) -> Program:
        program = self.get_program(db, program_id)
        program.is_active = False
        return self.repository.save(db, program)

    def restore_program(self, db: Session, program_id: UUID) -> Program:
        program = self.get_program(db, program_id)
        self._ensure_active_department(db, program.department_id)
        program.is_active = True
        return self.repository.save(db, program)

    def _ensure_active_department(self, db: Session, department_id: UUID) -> None:
        department = db.scalar(select(Department).where(Department.id == department_id))
        if department is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Department does not exist")
        if not department.is_active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Department is inactive")

    def _ensure_unique_code(self, db: Session, program_code: str, exclude_id: UUID | None = None) -> None:
        existing = self.repository.get_by_code(db, program_code)
        if existing is not None and existing.id != exclude_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Program code already exists")


program_service = ProgramService()
