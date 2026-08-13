import { describe, expect, it } from "vitest";
import { laboratoryAvailabilityExportRows } from "@/lib/laboratory-availability-export";

describe("laboratory availability CSV export", () => {
  it("exports business keys and compact blocked periods without UUID columns", () => {
    const rows = laboratoryAvailabilityExportRows(
      [{ id: "lab-id", laboratory_code: "LAB3201", laboratory_name: "Power Lab", room_number: "3201", owning_department_id: "dep-id", availability_mode: "EXCEPT_BLOCKED" }],
      [{ id: "dep-id", department_code: "EEE" }],
      [{ id: "term-id", academic_year: "2026-27", term_name: "I-I" }],
      [{ id: "mon-id", day_name: "Monday", sequence_number: 1 }],
      [{ id: "slot-id", laboratory_id: "lab-id", academic_term_id: "term-id", working_day_id: "mon-id", period_number: 2, availability_type: "BLOCKED", is_active: true }],
    );
    expect(rows).toEqual([expect.objectContaining({ laboratory_code: "LAB3201", department_code: "EEE", academic_term_code: "2026-27 | I-I", blocked_periods: "Mon:P2", allowed_periods: "" })]);
    expect(Object.keys(rows[0]).some((key) => key.endsWith("_id"))).toBe(false);
  });
});
