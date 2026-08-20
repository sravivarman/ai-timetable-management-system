from datetime import datetime,timezone
from uuid import UUID,uuid4
from sqlalchemy import CheckConstraint,DateTime,ForeignKey,Integer,String,JSON,func
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.types import Uuid
from app.db.base import Base


def utc_now() -> datetime:
 return datetime.now(timezone.utc)


class ValidationRun(Base):
 __tablename__="validation_runs";__table_args__=(CheckConstraint("(scheduling_mode = 'WEEKLY' AND scheduling_slot_id IS NULL) OR (scheduling_mode = 'SLOT_BASED' AND scheduling_slot_id IS NOT NULL)",name="ck_validation_run_scheduling_mode_slot"),);id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);academic_term_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("academic_terms.id"));scope_type:Mapped[str]=mapped_column(String(20));department_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("departments.id"));program_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("programs.id"));section_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("sections.id"));scheduling_mode:Mapped[str]=mapped_column(String(20),default="WEEKLY",nullable=False,index=True);scheduling_slot_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("scheduling_slots.id",ondelete="RESTRICT"),index=True);status:Mapped[str]=mapped_column(String(20));total_checks:Mapped[int]=mapped_column(Integer);passed_checks:Mapped[int]=mapped_column(Integer);failed_checks:Mapped[int]=mapped_column(Integer);warning_checks:Mapped[int]=mapped_column(Integer);started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utc_now,server_default=func.now());completed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utc_now,server_default=func.now());created_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utc_now,server_default=func.now())
class ValidationIssue(Base):
 __tablename__="validation_issues";id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);validation_run_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("validation_runs.id"));severity:Mapped[str]=mapped_column(String(10));issue_code:Mapped[str]=mapped_column(String(100));entity_type:Mapped[str|None]=mapped_column(String(100));entity_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True));message:Mapped[str]=mapped_column(String(1000));details:Mapped[dict|None]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utc_now,server_default=func.now())
