import { describe, expect, it } from "vitest";
import { resolveSlotRequirementRows, SLOT_REQUIREMENT_CSV_HEADERS, slotRequirementTemplate } from "@/lib/slot-requirement-csv";
import type { SlotRequirementMatrix } from "@/lib/types";

const slot = (id: string, code: string) => ({ id, academic_term_id: "term", slot_code: code, slot_name: code, sequence_number: Number(code.slice(1)), start_date: "2026-08-01", end_date: "2026-08-31", working_date_count: 6, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" });
const matrix: SlotRequirementMatrix = {
  slots: [slot("slot-1", "S01"), slot("slot-2", "S02")],
  rows: [{ course_offering_id: "offering-1", section_id: "section-1", course_code: "A9001", course_name: "Mathematics", course_type: "THEORY", section_code: "CSE-A", section_name: "A", allocated_to_slots: 0, remaining_to_allocate: null, over_allocated: 0, reconciliation_status: "NOT_CONFIGURED", cells: [
    { scheduling_slot_id: "slot-1", requirement_id: null, sessions_required: null, status: "MISSING" },
    { scheduling_slot_id: "slot-2", requirement_id: "requirement-2", sessions_required: 0, status: "CONFIGURED_ZERO" },
  ] }],
  completeness: [],
};

describe("Slot requirement business-key CSV", () => {
  it("contains no UUID columns and resolves business keys to internal IDs", () => {
    expect(SLOT_REQUIREMENT_CSV_HEADERS.some((header) => header.endsWith("_id"))).toBe(false);
    expect(Object.keys(slotRequirementTemplate()[0]).some((header) => header.endsWith("_id"))).toBe(false);
    const [resolved] = resolveSlotRequirementRows([{ academic_term: "2026-27 I-I", slot_code: "s01", course_code: "a9001", section_code: "cse-a", sessions_required: "4" }], matrix, "2026-27 I-I");
    expect(resolved).toMatchObject({ status: "NEW", scheduling_slot_id: "slot-1", course_offering_id: "offering-1", sessions_required: 4 });
  });

  it("preserves explicit zero and distinguishes identical from changed", () => {
    const [identical] = resolveSlotRequirementRows([{ academic_term: "2026-27 I-I", slot_code: "S02", course_code: "A9001", section_code: "CSE-A", sessions_required: "0" }], matrix, "2026-27 I-I");
    const [changed] = resolveSlotRequirementRows([{ academic_term: "2026-27 I-I", slot_code: "S02", course_code: "A9001", section_code: "CSE-A", sessions_required: "3" }], matrix, "2026-27 I-I");
    expect(identical.status).toBe("IDENTICAL");
    expect(identical.sessions_required).toBe(0);
    expect(changed.status).toBe("CHANGED");
  });

  it("rejects unknown keys, invalid values, and contradictory duplicates", () => {
    const rows = resolveSlotRequirementRows([
      { academic_term: "2026-27 I-I", slot_code: "UNKNOWN", course_code: "A9001", section_code: "CSE-A", sessions_required: "1" },
      { academic_term: "2026-27 I-I", slot_code: "S01", course_code: "A9001", section_code: "CSE-A", sessions_required: "-1" },
      { academic_term: "2026-27 I-I", slot_code: "S01", course_code: "A9001", section_code: "CSE-A", sessions_required: "1" },
      { academic_term: "2026-27 I-I", slot_code: "S01", course_code: "A9001", section_code: "CSE-A", sessions_required: "2" },
    ], matrix, "2026-27 I-I");
    expect(rows[0].status).toBe("INVALID");
    expect(rows[1].status).toBe("INVALID");
    expect(rows[2].status).toBe("CONFLICT");
    expect(rows[3].status).toBe("CONFLICT");
  });
});
