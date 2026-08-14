import { describe, expect, it } from "vitest";
import { normalizeEntityLookupParams, normalizeOptionalEntityFilter, normalizeReportFilters } from "@/lib/report-filter-normalization";

describe("administrative report filter normalization", () => {
  it.each(["academic_term_id", "department_id", "program_id", "section_id", "course_id", "faculty_id", "faculty_department_id"])("omits All/empty values for %s", (key) => {
    expect(normalizeReportFilters({ [key]: "" })).toEqual({});
    expect(normalizeReportFilters({ [key]: "All" })).toEqual({});
    expect(normalizeReportFilters({ [key]: undefined })).toEqual({});
  });

  it("preserves valid entity IDs and meaningful enum All semantics", () => {
    expect(normalizeOptionalEntityFilter(" 8e593104-00be-4ad6-a2a4-1e090b34004e ")).toBe("8e593104-00be-4ad6-a2a4-1e090b34004e");
    expect(normalizeReportFilters({ department_id: "8e593104-00be-4ad6-a2a4-1e090b34004e", status: "ALL" })).toEqual({ department_id: "8e593104-00be-4ad6-a2a4-1e090b34004e", status: "ALL" });
  });

  it("never sends empty UUID query parameters to dependent lookup APIs", () => {
    expect(normalizeEntityLookupParams({ academic_term_id: "", department_id: "All", program_id: undefined })).toEqual({});
    expect(normalizeEntityLookupParams({ department_id: "dept-1", program_id: "" })).toEqual({ department_id: "dept-1" });
  });
});
