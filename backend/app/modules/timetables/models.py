from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import Boolean,CheckConstraint,DateTime,ForeignKey,Integer,String,JSON,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.types import Uuid
from app.db.base import Base
class Timetable(Base):
 __tablename__="timetables";id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);academic_term_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("academic_terms.id"));scope_type:Mapped[str]=mapped_column(String(20));department_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True));program_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True));section_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True));name:Mapped[str]=mapped_column(String(255));status:Mapped[str]=mapped_column(String(20),default="DRAFT");active_version_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True));created_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
class TimetableVersion(Base):
 __tablename__="timetable_versions";__table_args__=(UniqueConstraint("timetable_id","version_number",name="uq_timetable_version_number"),)
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);timetable_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetables.id"));version_number:Mapped[int]=mapped_column(Integer);version_name:Mapped[str|None]=mapped_column(String(255));source_type:Mapped[str]=mapped_column(String(20));validation_run_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("validation_runs.id"));solver_status:Mapped[str]=mapped_column(String(20),default="NOT_STARTED");is_active:Mapped[bool]=mapped_column(Boolean,default=True);is_locked:Mapped[bool]=mapped_column(Boolean,default=False);created_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
class SolverInputSnapshot(Base):
 __tablename__="solver_input_snapshots";__table_args__=(UniqueConstraint("timetable_version_id","input_hash",name="uq_solver_snapshot_version_hash"),);id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);timetable_version_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetable_versions.id"),index=True);snapshot_json:Mapped[dict]=mapped_column(JSON);input_hash:Mapped[str]=mapped_column(String(64),index=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())


class TimetableEntry(Base):
 __tablename__="timetable_entries"
 __table_args__=(CheckConstraint("period_number BETWEEN 1 AND 7",name="ck_timetable_entry_period"),CheckConstraint("session_length IN (1,2,3)",name="ck_timetable_entry_session_length"),CheckConstraint("period_number + session_length - 1 <= 7",name="ck_timetable_entry_session_end"),CheckConstraint("entry_type IN ('THEORY','LABORATORY','PRACTICAL','CDC','LSM','MINI_PROJECT','PROJECT')",name="ck_timetable_entry_type"))
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
 timetable_version_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetable_versions.id",ondelete="CASCADE"),nullable=False,index=True)
 course_offering_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("course_offerings.id",ondelete="RESTRICT"),nullable=False,index=True)
 section_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("sections.id",ondelete="RESTRICT"),nullable=False,index=True)
 faculty_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("faculty.id",ondelete="RESTRICT"),index=True)
 laboratory_faculty_allocation_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("laboratory_faculty_allocations.id",ondelete="RESTRICT"))
 classroom_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("classrooms.id",ondelete="RESTRICT"),index=True)
 laboratory_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("laboratories.id",ondelete="RESTRICT"),index=True)
 student_batch_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("student_batches.id",ondelete="RESTRICT"),index=True)
 laboratory_rotation_block_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("laboratory_rotation_blocks.id",ondelete="RESTRICT"),index=True)
 laboratory_rotation_assignment_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("laboratory_rotation_assignments.id",ondelete="RESTRICT"),index=True)
 combined_teaching_event_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True),ForeignKey("combined_teaching_events.id",ondelete="CASCADE"),index=True)
 working_day_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("working_days.id",ondelete="RESTRICT"),nullable=False,index=True)
 period_number:Mapped[int]=mapped_column(Integer,nullable=False,index=True)
 session_length:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
 entry_type:Mapped[str]=mapped_column(String(20),nullable=False,index=True)
 is_manual:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False,index=True)
 is_locked:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False,index=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)


class SolverRun(Base):
 __tablename__="solver_runs"
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
 timetable_version_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetable_versions.id",ondelete="CASCADE"),nullable=False,index=True)
 solver_input_snapshot_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("solver_input_snapshots.id",ondelete="RESTRICT"),nullable=False,index=True)
 status:Mapped[str]=mapped_column(String(20),nullable=False,index=True)
 started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 runtime_seconds:Mapped[float|None]=mapped_column()
 objective_value:Mapped[float|None]=mapped_column()
 best_bound:Mapped[float|None]=mapped_column()
 generated_entry_count:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 message:Mapped[str|None]=mapped_column(String(1000))
 statistics_json:Mapped[dict|None]=mapped_column(JSON)
 created_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

class TimetableEntryAudit(Base):
 __tablename__="timetable_entry_audits"
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
 timetable_entry_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),nullable=False,index=True)
 timetable_version_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetable_versions.id",ondelete="CASCADE"),nullable=False,index=True)
 action_type:Mapped[str]=mapped_column(String(20),nullable=False,index=True)
 old_values_json:Mapped[dict|None]=mapped_column(JSON)
 new_values_json:Mapped[dict|None]=mapped_column(JSON)
 reason:Mapped[str|None]=mapped_column(String(1000))
 performed_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False,index=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

class TimetableStatusHistory(Base):
 __tablename__="timetable_status_history"
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
 timetable_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("timetables.id",ondelete="CASCADE"),nullable=False,index=True)
 from_status:Mapped[str]=mapped_column(String(20),nullable=False)
 to_status:Mapped[str]=mapped_column(String(20),nullable=False)
 reason:Mapped[str|None]=mapped_column(String(1000))
 performed_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False,index=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
