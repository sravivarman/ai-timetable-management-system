"""SQLAlchemy repository for academic programs."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.programs.models import Program


class ProgramRepository:
    def get(self, db: Session, program_id: UUID) -> Program | None:
        return db.scalar(select(Program).where(Program.id == program_id))

    def get_by_code(self, db: Session, program_code: str) -> Program | None:
        return db.scalar(select(Program).where(Program.program_code == program_code))

    def list(
        self,
        db: Session,
        *,
        search: str | None,
        department_id: UUID | None,
        include_inactive: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Program], int]:
        filters = []
        if department_id is not None:
            filters.append(Program.department_id == department_id)
        if not include_inactive:
            filters.append(Program.is_active.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Program.program_code.ilike(pattern), Program.program_name.ilike(pattern)))
        statement = select(Program).where(*filters).order_by(Program.program_code)
        total = int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        return list(db.scalars(statement.offset(offset).limit(limit))), total

    def save(self, db: Session, program: Program) -> Program:
        db.add(program)
        db.commit()
        db.refresh(program)
        return program
