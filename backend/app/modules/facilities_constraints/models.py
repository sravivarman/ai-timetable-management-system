from datetime import date,datetime
from uuid import UUID,uuid4
from sqlalchemy import Boolean,Date,DateTime,ForeignKey,Integer,String,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.types import Uuid
from app.db.base import Base
class SectionClassroomAssignment(Base):
 __tablename__="section_classroom_assignments";__table_args__=(UniqueConstraint("section_id","classroom_id","academic_term_id",name="uq_section_classroom_assignment"),)
 id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4);section_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("sections.id"),index=True);classroom_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("classrooms.id"),index=True);academic_term_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey("academic_terms.id"),index=True);is_primary:Mapped[bool]=mapped_column(Boolean,default=True);effective_from:Mapped[date|None]=mapped_column(Date);effective_to:Mapped[date|None]=mapped_column(Date);is_active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
from app.modules.resource_availability.models import ResourceAvailabilitySlot as LaboratoryAvailabilityBlock
