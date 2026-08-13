import { describe, expect, it } from "vitest";
import { academicTermLabel, sectionLabel, sectionTerm } from "@/lib/section-labels";

const term = { id: "term-1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1 };
const section = { section_code: "CSD-A", section_name: "A", academic_term_id: "term-1" };

describe("section labels", () => {
  it("uses the richest available academic-term label without repeating the section name", () => {
    expect(sectionLabel(section, term)).toBe("2026-27 I-I • CSD-A");
    expect(sectionLabel(section, term)).not.toContain("CSD-A · A");
  });

  it("falls back to the section code when term metadata is unavailable", () => {
    expect(sectionLabel(section)).toBe("CSD-A");
  });

  it("resolves the section academic term and can derive a year/semester label", () => {
    expect(sectionTerm(section, [term, { ...term, id: "term-2" }])).toEqual(term);
    expect(academicTermLabel({ academic_year: "2026-27", year_number: 1, semester_number: 2 })).toBe("2026-27 I Year II Semester");
  });
});
