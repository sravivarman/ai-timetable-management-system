"""Faculty persistence operations."""
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.modules.faculty.models import Faculty
class FacultyRepository:
    def get(self, db: Session, id: UUID) -> Faculty | None: return db.scalar(select(Faculty).where(Faculty.id == id))
    def by_code(self, db: Session, value: str) -> Faculty | None: return db.scalar(select(Faculty).where(Faculty.faculty_code == value))
    def by_email(self, db: Session, value: str) -> Faculty | None: return db.scalar(select(Faculty).where(Faculty.institutional_email == value.lower()))
    def by_user(self, db: Session, value: UUID) -> Faculty | None: return db.scalar(select(Faculty).where(Faculty.user_id == value))
    def list(self, db: Session, *, search, department_id, designation, is_active, offset, limit):
        filters=[]
        if search: filters.append(or_(Faculty.faculty_code.ilike(f"%{search}%"), Faculty.full_name.ilike(f"%{search}%"), Faculty.institutional_email.ilike(f"%{search}%")))
        for col,val in ((Faculty.department_id,department_id),(Faculty.designation,designation),(Faculty.is_active,is_active)):
            if val is not None: filters.append(col == val)
        stmt=select(Faculty).where(*filters).order_by(Faculty.faculty_code); total=int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        return list(db.scalars(stmt.offset(offset).limit(limit))),total
    def save(self, db, entity): db.add(entity); db.commit(); db.refresh(entity); return entity
