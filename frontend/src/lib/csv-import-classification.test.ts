import { describe, expect, it } from "vitest";
import { classifyImportRows, importSummary } from "@/lib/csv-import-classification";
import { masterConfigs } from "@/lib/master-data-config";
import type { MasterRecord } from "@/lib/master-data-api";
import type { ResolvedImportRow } from "@/lib/csv-import-resolution";

function row(payload: Record<string, unknown>, source: Record<string, string> = {}, errors: string[] = []): ResolvedImportRow {
  return { payload, source, internalRow: {}, references: [], errors };
}

describe("safe CSV row classification", () => {
  it("classifies NEW, IDENTICAL, CHANGED, INVALID, and CONFLICT with consistent counts", () => {
    const current: MasterRecord[] = [
      { id: "one", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true },
      { id: "two", department_code: "ECE", department_name: "Electronics", short_name: "ECE", is_active: true },
    ];
    const rows = classifyImportRows(masterConfigs.departments, [
      row({ department_code: "CIV", department_name: "Civil", short_name: "CIV" }, { department_code: "CIV" }),
      row({ department_code: "CSE", department_name: "Computer Science", short_name: "CSE" }, { department_code: "CSE" }),
      row({ department_code: "ECE", department_name: "Electronics and Communication", short_name: "ECE" }, { department_code: "ECE", department_name: "Electronics and Communication", short_name: "ECE" }),
      row({}, {}, ["Department code is required."]),
      row({ department_code: "EEE", department_name: "Electrical", short_name: "EEE" }, { department_code: "EEE" }),
      row({ department_code: "EEE", department_name: "Electrical Engineering", short_name: "EEE" }, { department_code: "EEE" }),
    ], { "/departments": current });
    expect(rows.map((item) => item.status)).toEqual(["NEW", "IDENTICAL", "CHANGED", "INVALID", "CONFLICT", "CONFLICT"]);
    expect(importSummary(rows)).toMatchObject({ total: 6, new: 1, changed: 1, identical: 1, invalid: 1, conflicts: 2 });
  });

  it("normalizes code case, email case, duplicate spaces, names, booleans, and unordered sets", () => {
    const existing = { id: "faculty-1", faculty_code: "VCE1261", full_name: "Dr. Ramesh Karnati", department_id: "department-1", designation: "Professor", institutional_email: "RAMESH@VCE.AC.IN", phone_number: null, minimum_weekly_workload: 0, maximum_weekly_workload: 18, maximum_periods_per_day: null, is_active: true };
    const result = classifyImportRows(masterConfigs.faculty, [row({ ...existing, faculty_code: "vce1261", full_name: "DR. RAMESH  KARNATI", institutional_email: "ramesh@vce.ac.in" }, { faculty_code: "vce1261", is_active: "TRUE" })], { "/faculty": [existing] });
    expect(result[0].status).toBe("IDENTICAL");
  });

  it("uses the offering—not faculty—as Theory Allocation identity", () => {
    const existing = { id: "allocation-1", course_offering_id: "offering-a", faculty_id: "faculty-old", is_active: true };
    const changed = classifyImportRows(masterConfigs["theory-allocations"], [row({ course_offering_id: "offering-a", faculty_id: "faculty-new" }, { course_code: "A9001", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", faculty_code: "VCE1880" })], { "/faculty-allocations/theory": [existing], "/faculty": [{ id: "faculty-old", faculty_code: "VCE1677", full_name: "Old Faculty" }, { id: "faculty-new", faculty_code: "VCE1880", full_name: "New Faculty" }] });
    expect(changed[0].status).toBe("CHANGED");
    expect(changed[0].differences.find((item) => item.field === "faculty_id")).toMatchObject({ existingLabel: "VCE1677 - Old Faculty", importedLabel: "VCE1880 - New Faculty" });

    const independent = classifyImportRows(masterConfigs["theory-allocations"], [
      row({ course_offering_id: "offering-a", faculty_id: "faculty-old" }, { course_code: "A", section_code: "CSE-A", academic_term_code: "TERM" }),
      row({ course_offering_id: "offering-b", faculty_id: "faculty-old" }, { course_code: "A", section_code: "CSE-B", academic_term_code: "TERM" }),
      row({ course_offering_id: "offering-c", faculty_id: "faculty-new" }, { course_code: "C", section_code: "CSE-A", academic_term_code: "TERM" }),
      row({ course_offering_id: "offering-d", faculty_id: "faculty-new" }, { course_code: "D", section_code: "CSE-B", academic_term_code: "TERM" }),
    ], { "/faculty-allocations/theory": [] });
    expect(independent.every((item) => item.status === "NEW")).toBe(true);
  });

  it("marks contradictory duplicate Theory assignments as CONFLICT and never chooses a winner", () => {
    const result = classifyImportRows(masterConfigs["theory-allocations"], [
      row({ course_offering_id: "offering-a", faculty_id: "faculty-a" }, { course_code: "A9001", section_code: "CSE-A", academic_term_code: "TERM", faculty_code: "VCE100" }),
      row({ course_offering_id: "offering-a", faculty_id: "faculty-b" }, { course_code: "A9001", section_code: "CSE-A", academic_term_code: "TERM", faculty_code: "VCE200" }),
    ], { "/faculty-allocations/theory": [] });
    expect(result.map((item) => item.status)).toEqual(["CONFLICT", "CONFLICT"]);
  });

  it("deduplicates exact input safely while retaining one NEW write", () => {
    const duplicate = row({ department_code: "CSE", department_name: "Computer Science", short_name: "CSE" }, { department_code: "CSE" });
    const result = classifyImportRows(masterConfigs.departments, [duplicate, duplicate], { "/departments": [] });
    expect(result.map((item) => item.status)).toEqual(["NEW", "IDENTICAL"]);
    expect(result[1].messages.join(" ")).toContain("Duplicate of CSV row 2");
  });

  it("preserves independent Activity MAIN/SUPPORTING identities and classifies mutable relationship changes", () => {
    const main = { id: "main", course_offering_id: "offering", faculty_id: "faculty-main", role_type: "MAIN", required_with_main_faculty_id: null, alternative_group_code: null, minimum_sessions_per_week: 1, maximum_sessions_per_week: 1, is_active: true };
    const supporting = { id: "support", course_offering_id: "offering", faculty_id: "faculty-support", role_type: "SUPPORTING", required_with_main_faculty_id: "faculty-main", alternative_group_code: null, minimum_sessions_per_week: 1, maximum_sessions_per_week: 1, is_active: true };
    const result = classifyImportRows(masterConfigs["laboratory-allocations"], [
      row({ ...main }, { course_code: "A9205", section_code: "INF-A", academic_term_code: "TERM", faculty_code: "VCE1009", role_type: "MAIN" }),
      row({ ...supporting, maximum_sessions_per_week: 2 }, { course_code: "A9205", section_code: "INF-A", academic_term_code: "TERM", faculty_code: "VCE1837", role_type: "SUPPORTING", maximum_sessions_per_week: "2" }),
      row({ course_offering_id: "offering", faculty_id: "faculty-new", role_type: "SUPPORTING", required_with_main_faculty_id: "faculty-main", alternative_group_code: "ALT-A", minimum_sessions_per_week: 1, maximum_sessions_per_week: 1 }, { course_code: "A9205", section_code: "INF-A", academic_term_code: "TERM", faculty_code: "VCE2000", role_type: "SUPPORTING" }),
    ], { "/faculty-allocations/laboratory": [main, supporting] });
    expect(result.map((item) => item.status)).toEqual(["IDENTICAL", "CHANGED", "NEW"]);
  });

  it("classifies solver-semantic laboratory and offering-set changes as CHANGED", () => {
    const laboratory = { id: "lab", laboratory_code: "5A01", laboratory_name: "Workshop", room_number: "5A01", owning_department_id: "department", is_shareable_across_departments: true, concurrent_usage_mode: "EXCLUSIVE", capacity: 60, availability_mode: "ALL_PERIODS", is_active: true };
    const labResult = classifyImportRows(masterConfigs.laboratories, [row({ ...laboratory, concurrent_usage_mode: "CAPACITY_SHARED" }, { laboratory_code: "5A01", concurrent_usage_mode: "CAPACITY_SHARED" })], { "/laboratories": [laboratory] });
    expect(labResult[0].status).toBe("CHANGED");
    expect(labResult[0].differences.map((item) => item.field)).toContain("concurrent_usage_mode");

    const offering = { id: "offering", course_id: "course", section_id: "section", academic_term_id: "term", weekly_periods_override: null, is_mandatory: true, elective_group_name: null, laboratory_selection_mode: "RESTRICTED", allowed_laboratory_ids: ["3117", "5014"], laboratory_override_id: null, is_active: true };
    const offeringResult = classifyImportRows(masterConfigs["course-offerings"], [row({ ...offering, allowed_laboratory_ids: ["1117", "3117"] }, { course_code: "A9008", section_code: "ECE-A", academic_term_code: "TERM", allowed_laboratory_codes: "1117|3117" })], { "/course-offerings": [offering] });
    expect(offeringResult[0].status).toBe("CHANGED");
    expect(offeringResult[0].differences.map((item) => item.field)).toContain("allowed_laboratory_ids");
  });

  it("classifies is_active changes as CHANGED rather than deactivating implicitly", () => {
    const existing = { id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true };
    const result = classifyImportRows(masterConfigs.departments, [row({ department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: false }, { department_code: "CSE", is_active: "FALSE" })], { "/departments": [existing] });
    expect(result[0].status).toBe("CHANGED");
    expect(result[0].differences.map((item) => item.field)).toContain("is_active");
  });
});
