"""Mode-specific academic demand feeding the shared scheduling engine."""


class WeeklyDemandBuilder:
    mode = "WEEKLY"

    @staticmethod
    def sessions(offering: dict) -> int:
        return int(offering.get("sessions_per_week") or offering.get("lab_sessions_per_week") or 0)


class SlotDemandBuilder:
    mode = "SLOT_BASED"

    @staticmethod
    def sessions(offering: dict) -> int:
        value = offering.get("slot_sessions_required")
        if value is None:
            raise ValueError(f"Missing Slot Session Requirement for {offering.get('course_code', 'Course Offering')}")
        return int(value)


def demand_builder(snapshot: dict):
    return SlotDemandBuilder() if snapshot.get("metadata", {}).get("scheduling_mode") == "SLOT_BASED" else WeeklyDemandBuilder()
