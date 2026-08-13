"""Queries for combined teaching groups."""

from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import CombinedTeachingGroup, CombinedTeachingGroupMember


class CombinedTeachingRepository:
    def get(self, db: Session, group_id: UUID) -> CombinedTeachingGroup | None:
        return db.get(CombinedTeachingGroup, group_id)

    def members(self, db: Session, group_id: UUID, active_only: bool = True):
        query = select(CombinedTeachingGroupMember).where(CombinedTeachingGroupMember.combined_teaching_group_id == group_id)
        if active_only:
            query = query.where(CombinedTeachingGroupMember.is_active.is_(True))
        return list(db.scalars(query.order_by(CombinedTeachingGroupMember.course_offering_id, CombinedTeachingGroupMember.id)))

    def list(self, db: Session, *, search: str | None, academic_term_id: UUID | None, course_id: UUID | None, faculty_id: UUID | None, is_active: bool | None, page: int, page_size: int):
        query = select(CombinedTeachingGroup)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(or_(CombinedTeachingGroup.group_code.ilike(pattern), CombinedTeachingGroup.group_name.ilike(pattern)))
        for column, value in ((CombinedTeachingGroup.academic_term_id, academic_term_id), (CombinedTeachingGroup.course_id, course_id), (CombinedTeachingGroup.faculty_id, faculty_id), (CombinedTeachingGroup.is_active, is_active)):
            if value is not None:
                query = query.where(column == value)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = list(db.scalars(query.order_by(CombinedTeachingGroup.group_code, CombinedTeachingGroup.id).offset((page - 1) * page_size).limit(page_size)))
        return rows, total


combined_teaching_repository = CombinedTeachingRepository()
