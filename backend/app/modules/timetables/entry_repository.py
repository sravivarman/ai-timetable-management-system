from math import ceil
from sqlalchemy import delete,func,select
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.timetables.models import TimetableEntry

class TimetableEntryRepository:
 def get(self,db,entry_id):return db.scalar(select(TimetableEntry).where(TimetableEntry.id==entry_id))
 def list(self,db,version_id,page,page_size,**filters):
  query=select(TimetableEntry).join(WorkingDay,WorkingDay.id==TimetableEntry.working_day_id).where(TimetableEntry.timetable_version_id==version_id,*[getattr(TimetableEntry,key)==value for key,value in filters.items() if value is not None]).order_by(WorkingDay.sequence_number,TimetableEntry.period_number,TimetableEntry.section_id,TimetableEntry.id)
  total=int(db.scalar(select(func.count()).select_from(query.subquery()))or 0)
  return {"items":list(db.scalars(query.offset((page-1)*page_size).limit(page_size))),"total":total,"page":page,"page_size":page_size,"pages":ceil(total/page_size)if total else 0}
 def overlapping(self,db,version_id,working_day_id,start,end,exclude_id=None):
  query=select(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id,TimetableEntry.working_day_id==working_day_id,TimetableEntry.period_number<=end,(TimetableEntry.period_number+TimetableEntry.session_length-1)>=start)
  if exclude_id is not None:query=query.where(TimetableEntry.id!=exclude_id)
  return list(db.scalars(query))
 def remove_replaceable_generated(self,db,version_id):
  db.execute(delete(TimetableEntry).where(TimetableEntry.timetable_version_id==version_id,TimetableEntry.is_manual.is_(False),TimetableEntry.is_locked.is_(False)))
  db.flush()

entry_repository=TimetableEntryRepository()
