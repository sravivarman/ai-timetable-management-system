from datetime import datetime,time
from uuid import UUID,uuid4
from sqlalchemy import Boolean,CheckConstraint,DateTime,Index,Integer,String,Time,UniqueConstraint,func,text
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.types import Uuid
from app.db.base import Base
class WorkingDay(Base):
 __tablename__="working_days";id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);day_name:Mapped[str]=mapped_column(String(10),unique=True);sequence_number:Mapped[int]=mapped_column(Integer,unique=True);is_working_day:Mapped[bool]=mapped_column(Boolean,default=True);is_active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
class PeriodTiming(Base):
 __tablename__="period_timings";__table_args__=(UniqueConstraint("schedule_type","sequence_number",name="uq_period_timing_type_sequence"),Index("uq_period_timing_instructional_number","schedule_type","period_number",unique=True,postgresql_where=text("period_number IS NOT NULL")),CheckConstraint("(is_instructional AND period_number BETWEEN 1 AND 7) OR (NOT is_instructional AND period_number IS NULL AND break_type IS NOT NULL)",name="ck_period_timing_instructional_or_break"))
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);schedule_type:Mapped[str]=mapped_column(String(20));period_number:Mapped[int|None]=mapped_column(Integer);start_time:Mapped[time]=mapped_column(Time);end_time:Mapped[time]=mapped_column(Time);duration_minutes:Mapped[int]=mapped_column(Integer);is_instructional:Mapped[bool]=mapped_column(Boolean,default=True);break_type:Mapped[str|None]=mapped_column(String(20));sequence_number:Mapped[int]=mapped_column(Integer);is_active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
