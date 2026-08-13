"""Backward-compatible laboratory facade over the unified resource engine."""
from app.modules.resource_availability.service import VALID_MODES, availability_service, snapshot_resource_is_available


def effective_availability_mode(laboratory, db=None, academic_term_id=None):
    if db is not None and academic_term_id is not None:
        return availability_service.effective_mode(db,"LABORATORY",laboratory.id,academic_term_id)
    mode=getattr(laboratory,"availability_mode",None)
    if mode in VALID_MODES:return mode
    return "ALL_PERIODS" if getattr(laboratory,"is_available_all_periods",True) else "EXCEPT_BLOCKED"


def laboratory_slot_is_available(db,laboratory,academic_term_id,working_day_id,period_number):
    return availability_service.is_available(db,"LABORATORY",laboratory.id,academic_term_id,working_day_id,period_number)


def snapshot_slot_is_available(laboratory,slots,day_id,period):
    # Legacy snapshots use a laboratory-only tuple shape.
    generic={("LABORATORY",laboratory_id,working_day_id,period_number,slot_type) for laboratory_id,working_day_id,period_number,slot_type in slots}
    mode=laboratory.get("availability_mode")
    if mode not in VALID_MODES:mode="ALL_PERIODS" if laboratory.get("is_available_all_periods",True) else "EXCEPT_BLOCKED"
    return snapshot_resource_is_available("LABORATORY",laboratory["id"],{("LABORATORY",laboratory["id"]):mode},generic,day_id,period)
