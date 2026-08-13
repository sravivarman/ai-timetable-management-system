"""Pure regression tests for snapshot-side laboratory availability semantics."""
import unittest

from app.modules.facilities.availability import snapshot_slot_is_available


class LaboratoryAvailabilityModeTests(unittest.TestCase):
    def test_all_periods_ignores_legacy_rows(self):
        laboratory = {"id": "lab", "availability_mode": "ALL_PERIODS"}
        self.assertTrue(snapshot_slot_is_available(laboratory, {("lab", "sat", 1, "BLOCKED")}, "sat", 1))

    def test_except_blocked_supports_maintenance_and_entire_saturday(self):
        laboratory = {"id": "lab", "availability_mode": "EXCEPT_BLOCKED"}
        slots = {("lab", "mon", 1, "BLOCKED"), ("lab", "mon", 2, "BLOCKED")} | {("lab", "sat", period, "BLOCKED") for period in range(1, 8)}
        self.assertFalse(snapshot_slot_is_available(laboratory, slots, "mon", 1))
        self.assertTrue(snapshot_slot_is_available(laboratory, slots, "wed", 6))
        self.assertTrue(all(not snapshot_slot_is_available(laboratory, slots, "sat", period) for period in range(1, 8)))

    def test_only_selected_supports_afternoon_only_availability(self):
        laboratory = {"id": "lab", "availability_mode": "ONLY_SELECTED"}
        slots = {("lab", day, period, "ALLOWED") for day in ("tue", "thu") for period in (4, 5, 6)}
        self.assertFalse(snapshot_slot_is_available(laboratory, slots, "tue", 1))
        self.assertTrue(snapshot_slot_is_available(laboratory, slots, "tue", 5))
        self.assertFalse(snapshot_slot_is_available(laboratory, slots, "wed", 5))

    def test_legacy_false_remains_except_blocked(self):
        laboratory = {"id": "lab", "is_available_all_periods": False}
        self.assertFalse(snapshot_slot_is_available(laboratory, {("lab", "mon", 3, "BLOCKED")}, "mon", 3))
        self.assertTrue(snapshot_slot_is_available(laboratory, set(), "mon", 3))


if __name__ == "__main__":
    unittest.main()
