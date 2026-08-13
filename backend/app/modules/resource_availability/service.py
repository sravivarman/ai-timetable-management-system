from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.academic_terms.models import AcademicTerm
from app.modules.facilities.models import Laboratory
from app.modules.resource_availability.models import ResourceAvailabilityProfile, ResourceAvailabilitySlot
from app.modules.resource_availability.registry import RESOURCE_REGISTRY, registration
from app.modules.schedule_configuration.models import WorkingDay

VALID_MODES = {"ALL_PERIODS", "EXCEPT_BLOCKED", "ONLY_SELECTED"}


class AvailabilityService:
    def normalize_type(self, resource_type: str) -> str:
        value = resource_type.upper()
        if value not in RESOURCE_REGISTRY:
            raise HTTPException(422, f"RESOURCE_INVALID_TYPE: unsupported resource type '{resource_type}'")
        # Named room/faculty categories currently share their physical master.
        # Canonicalizing here makes them solver-safe without branching the
        # persistence or scheduling architecture.
        return registration(value).concrete_type

    def resource(self, db, resource_type: str, resource_id, active=True):
        kind = self.normalize_type(resource_type); item = db.get(registration(kind).model, resource_id)
        if not item: raise HTTPException(404, "Resource not found")
        if active and not item.is_active: raise HTTPException(422, "Resource must be active")
        return kind, item

    def term(self, db, academic_term_id, active=True):
        item = db.get(AcademicTerm, academic_term_id)
        if not item: raise HTTPException(404, "Academic term not found")
        if active and not item.is_active: raise HTTPException(422, "Academic term must be active")
        return item

    def profile(self, db, resource_type, resource_id, academic_term_id):
        kind = self.normalize_type(resource_type)
        return db.scalar(select(ResourceAvailabilityProfile).where(ResourceAvailabilityProfile.resource_type == kind, ResourceAvailabilityProfile.resource_id == resource_id, ResourceAvailabilityProfile.academic_term_id == academic_term_id, ResourceAvailabilityProfile.is_active.is_(True)))

    def effective_mode(self, db, resource_type, resource_id, academic_term_id):
        profile = self.profile(db, resource_type, resource_id, academic_term_id)
        if profile: return profile.availability_mode
        kind, item = self.resource(db, resource_type, resource_id, active=False)
        if kind == "LABORATORY":
            mode = getattr(item, "availability_mode", None)
            if mode in VALID_MODES: return mode
            return "ALL_PERIODS" if getattr(item, "is_available_all_periods", True) else "EXCEPT_BLOCKED"
        return "ALL_PERIODS"

    def set_mode(self, db, resource_type, resource_id, academic_term_id, mode):
        kind, resource = self.resource(db, resource_type, resource_id); self.term(db, academic_term_id)
        if mode not in VALID_MODES: raise HTTPException(422, "RESOURCE_INVALID_MODE: availability mode is invalid")
        profile = self.profile(db, kind, resource_id, academic_term_id); now = datetime.now(timezone.utc)
        previous = self.effective_mode(db, kind, resource_id, academic_term_id)
        if profile is None:
            profile = ResourceAvailabilityProfile(resource_type=kind, resource_id=resource_id, academic_term_id=academic_term_id, availability_mode=mode, created_at=now, updated_at=now); db.add(profile)
        else: profile.availability_mode=mode; profile.updated_at=now
        if previous != mode:
            for slot in self.slots(db, kind, resource_id, academic_term_id, True): slot.is_active=False; slot.updated_at=now
        if kind == "LABORATORY": resource.availability_mode=mode; resource.is_available_all_periods=mode == "ALL_PERIODS"
        db.commit(); db.refresh(profile); return profile

    def slots(self, db, resource_type=None, resource_id=None, academic_term_id=None, is_active=True, working_day_id=None, period_number=None, availability_type=None):
        query=select(ResourceAvailabilitySlot)
        for column,value in ((ResourceAvailabilitySlot.resource_type,self.normalize_type(resource_type) if resource_type else None),(ResourceAvailabilitySlot.resource_id,resource_id),(ResourceAvailabilitySlot.academic_term_id,academic_term_id),(ResourceAvailabilitySlot.working_day_id,working_day_id),(ResourceAvailabilitySlot.period_number,period_number),(ResourceAvailabilitySlot.availability_type,availability_type),(ResourceAvailabilitySlot.is_active,is_active)):
            if value is not None: query=query.where(column==value)
        return list(db.scalars(query.order_by(ResourceAvailabilitySlot.resource_type,ResourceAvailabilitySlot.resource_id,ResourceAvailabilitySlot.working_day_id,ResourceAvailabilitySlot.period_number,ResourceAvailabilitySlot.id)))

    def create_slot(self, db, values):
        kind,_=self.resource(db,values.resource_type,values.resource_id);self.term(db,values.academic_term_id);day=db.get(WorkingDay,values.working_day_id)
        if not day or not day.is_active or not day.is_working_day:raise HTTPException(422,"Working day must be active")
        mode=self.effective_mode(db,kind,values.resource_id,values.academic_term_id)
        desired="ONLY_SELECTED" if values.availability_type=="ALLOWED" else "EXCEPT_BLOCKED"
        if mode=="ALL_PERIODS":self.set_mode(db,kind,values.resource_id,values.academic_term_id,desired);mode=desired
        if (mode=="EXCEPT_BLOCKED" and values.availability_type!="BLOCKED") or (mode=="ONLY_SELECTED" and values.availability_type!="ALLOWED"):raise HTTPException(422,f"RESOURCE_AVAILABILITY_CONFLICT: {mode} contains incompatible slot type")
        if self._duplicate(db,kind,values.resource_id,values.academic_term_id,values.working_day_id,values.period_number):raise HTTPException(409,"Active resource availability slot already exists")
        slot=ResourceAvailabilitySlot(**values.model_dump(exclude={"resource_type"}),resource_type=kind,created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc));db.add(slot);db.commit();db.refresh(slot);return slot

    def get_slot(self,db,slot_id):
        slot=db.get(ResourceAvailabilitySlot,slot_id)
        if not slot:raise HTTPException(404,"Resource availability slot not found")
        return slot

    def update_slot(self,db,slot_id,values):
        slot=self.get_slot(db,slot_id);data=values.model_dump(exclude_unset=True);period=data.get("period_number",slot.period_number);slot_type=data.get("availability_type",slot.availability_type);mode=self.effective_mode(db,slot.resource_type,slot.resource_id,slot.academic_term_id)
        if (mode=="EXCEPT_BLOCKED" and slot_type!="BLOCKED") or (mode=="ONLY_SELECTED" and slot_type!="ALLOWED") or mode=="ALL_PERIODS":raise HTTPException(422,"RESOURCE_AVAILABILITY_CONFLICT: slot does not match availability mode")
        if self._duplicate(db,slot.resource_type,slot.resource_id,slot.academic_term_id,slot.working_day_id,period,slot.id):raise HTTPException(409,"Active resource availability slot already exists")
        for key,value in data.items():setattr(slot,key,value)
        slot.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(slot);return slot

    def delete_slot(self,db,slot_id):
        slot=self.get_slot(db,slot_id);slot.is_active=False;slot.updated_at=datetime.now(timezone.utc);db.commit()

    def restore_slot(self,db,slot_id):
        slot=self.get_slot(db,slot_id);self.resource(db,slot.resource_type,slot.resource_id);self.term(db,slot.academic_term_id)
        if self._duplicate(db,slot.resource_type,slot.resource_id,slot.academic_term_id,slot.working_day_id,slot.period_number,slot.id):raise HTTPException(409,"Active resource availability slot already exists")
        mode=self.effective_mode(db,slot.resource_type,slot.resource_id,slot.academic_term_id)
        if (mode=="EXCEPT_BLOCKED" and slot.availability_type!="BLOCKED") or (mode=="ONLY_SELECTED" and slot.availability_type!="ALLOWED") or mode=="ALL_PERIODS":raise HTTPException(422,"RESOURCE_AVAILABILITY_CONFLICT: slot does not match availability mode")
        slot.is_active=True;slot.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(slot);return slot

    def is_available(self,db,resource_type,resource_id,academic_term_id,working_day_id,period_number):
        mode=self.effective_mode(db,resource_type,resource_id,academic_term_id)
        kind=self.normalize_type(resource_type);types=set(db.scalars(select(ResourceAvailabilitySlot.availability_type).where(ResourceAvailabilitySlot.resource_type==kind,ResourceAvailabilitySlot.resource_id==resource_id,ResourceAvailabilitySlot.academic_term_id==academic_term_id,ResourceAvailabilitySlot.working_day_id==working_day_id,ResourceAvailabilitySlot.period_number==period_number,ResourceAvailabilitySlot.is_active.is_(True))))
        if mode=="ALL_PERIODS":
            # Compatibility for legacy/directly inserted faculty records. API
            # writes are mirrored into generic slots, but historical snapshots
            # and test fixtures can still contain only the old representation.
            if kind=="FACULTY":
                from app.modules.faculty_scheduling.models import FacultyAvailability
                day=db.get(WorkingDay,working_day_id)
                if day and db.scalar(select(FacultyAvailability.id).where(FacultyAvailability.faculty_id==resource_id,FacultyAvailability.academic_term_id==academic_term_id,FacultyAvailability.day_of_week==day.day_name,FacultyAvailability.period_number==period_number,FacultyAvailability.availability_type=="unavailable",FacultyAvailability.is_active.is_(True))):return False
            return True
        if mode=="EXCEPT_BLOCKED":return "BLOCKED" not in types
        if mode=="ONLY_SELECTED":return "ALLOWED" in types
        return False

    def list_profiles(self,db,page,page_size,resource_type=None,resource_id=None,academic_term_id=None,is_active=True):
        query=select(ResourceAvailabilityProfile)
        for column,value in ((ResourceAvailabilityProfile.resource_type,self.normalize_type(resource_type) if resource_type else None),(ResourceAvailabilityProfile.resource_id,resource_id),(ResourceAvailabilityProfile.academic_term_id,academic_term_id),(ResourceAvailabilityProfile.is_active,is_active)):
            if value is not None:query=query.where(column==value)
        total=int(db.scalar(select(func.count()).select_from(query.subquery()))or 0);items=list(db.scalars(query.order_by(ResourceAvailabilityProfile.resource_type,ResourceAvailabilityProfile.resource_id,ResourceAvailabilityProfile.id).offset((page-1)*page_size).limit(page_size)));return {"items":items,"total":total,"page":page,"page_size":page_size,"pages":(total+page_size-1)//page_size}

    def list_slots(self,db,page,page_size,**filters):
        items=self.slots(db,**filters);total=len(items);return {"items":items[(page-1)*page_size:page*page_size],"total":total,"page":page,"page_size":page_size,"pages":(total+page_size-1)//page_size}

    def validate(self,db,resource_type,resource_id,academic_term_id):
        kind=self.normalize_type(resource_type);mode=self.effective_mode(db,kind,resource_id,academic_term_id);slots=self.slots(db,kind,resource_id,academic_term_id,True);issues=[]
        if mode not in VALID_MODES:issues.append(("RESOURCE_INVALID_MODE","ERROR","Availability mode is invalid"));return issues
        expected=None if mode=="ALL_PERIODS" else ("BLOCKED" if mode=="EXCEPT_BLOCKED" else "ALLOWED")
        if (expected is None and slots) or (expected and any(slot.availability_type!=expected for slot in slots)):issues.append(("RESOURCE_AVAILABILITY_CONFLICT","ERROR","Availability slots conflict with the selected mode"))
        if mode=="ONLY_SELECTED" and not any(slot.availability_type=="ALLOWED" for slot in slots):issues.append(("RESOURCE_SELECTED_PERIODS_EMPTY","ERROR","At least one allowed period is required"))
        days=list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))))
        if days and not any(self.is_available(db,kind,resource_id,academic_term_id,day.id,period) for day in days for period in range(1,8)):issues.append(("RESOURCE_NO_AVAILABLE_PERIODS","ERROR","Resource has no available instructional periods"))
        return issues

    def _duplicate(self,db,kind,resource_id,term_id,day_id,period,exclude=None):
        query=select(ResourceAvailabilitySlot.id).where(ResourceAvailabilitySlot.resource_type==kind,ResourceAvailabilitySlot.resource_id==resource_id,ResourceAvailabilitySlot.academic_term_id==term_id,ResourceAvailabilitySlot.working_day_id==day_id,ResourceAvailabilitySlot.period_number==period,ResourceAvailabilitySlot.is_active.is_(True))
        if exclude:query=query.where(ResourceAvailabilitySlot.id!=exclude)
        return db.scalar(query)


availability_service=AvailabilityService()


def snapshot_resource_is_available(resource_type,resource_id,modes,slots,day_id,period):
    mode=modes.get((resource_type,resource_id),"ALL_PERIODS")
    if mode=="ALL_PERIODS":return True
    if mode=="EXCEPT_BLOCKED":return (resource_type,resource_id,day_id,period,"BLOCKED") not in slots
    return (resource_type,resource_id,day_id,period,"ALLOWED") in slots
