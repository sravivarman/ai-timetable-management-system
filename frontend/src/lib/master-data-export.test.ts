import { describe, expect, it } from "vitest";
import { csvTemplateColumns, resolveCsvImportRow, type ImportLookupRecords } from "@/lib/csv-import-resolution";
import { serializeMasterDataExport } from "@/lib/master-data-export";
import { masterConfigs } from "@/lib/master-data-config";
import { resourceAvailabilityExportRows } from "@/lib/resource-availability-csv";

const ids = {
  term: "00000000-0000-4000-8000-000000000001", department: "00000000-0000-4000-8000-000000000002",
  program: "00000000-0000-4000-8000-000000000003", section: "00000000-0000-4000-8000-000000000004",
  faculty: "00000000-0000-4000-8000-000000000005", course: "00000000-0000-4000-8000-000000000006",
  classroom: "00000000-0000-4000-8000-000000000007", laboratory: "00000000-0000-4000-8000-000000000008",
  offering: "00000000-0000-4000-8000-000000000009", day: "00000000-0000-4000-8000-000000000010",
};
const term = { id: ids.term, academic_year: "2026-27", term_name: "I-I", is_active: true };
const department = { id: ids.department, department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true };
const program = { id: ids.program, department_id: ids.department, program_code: "CSE-UG", program_name: "B.Tech CSE", degree_type: "UG", duration_years: 4, is_active: true };
const classroom = { id: ids.classroom, room_number: "3204", room_name: "CSE Block", is_active: true };
const section = { id: ids.section, program_id: ids.program, academic_term_id: ids.term, primary_classroom_id: ids.classroom, section_code: "CSE-A", section_name: "A", student_strength: 72, is_active: true };
const faculty = { id: ids.faculty, faculty_code: "VCE042", full_name: "Dr. R. Kumar", department_id: ids.department, designation: "Professor", institutional_email: "kumar@vce.ac.in", minimum_weekly_workload: 8, maximum_weekly_workload: 16, is_active: true };
const laboratory = { id: ids.laboratory, laboratory_code: "CSE-LAB-01", laboratory_name: "Programming Lab", room_number: "3102", owning_department_id: ids.department, is_active: true };
const course = { id: ids.course, course_code: "CS301", course_name: "Operating Systems Laboratory", offering_department_id: ids.department, course_type: "LABORATORY", weekly_periods: 4, credits: 2, grouping_mode: "GROUPED", default_group_count: 2, session_duration: 2, sessions_per_week: 2, venue_requirement: "LABORATORY_ONLY", allows_same_course_double_period: false, eligible_laboratory_ids: [ids.laboratory], default_laboratory_id: ids.laboratory, counts_toward_workload: true, is_active: true, created_at: "2026-01-01", updated_at: "2026-01-02" };
const offering = { id: ids.offering, course_id: ids.course, section_id: ids.section, academic_term_id: ids.term, weekly_periods_override: 5, is_mandatory: true, is_common_theory: false, laboratory_selection_mode: "AUTO", laboratory_override_id: null, is_active: true };
const day = { id: ids.day, day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true };
const lookups: ImportLookupRecords = {
  "/academic-terms": [term], "/departments": [department], "/programs": [program], "/sections": [section],
  "/faculty": [faculty], "/courses": [course], "/classrooms": [classroom], "/laboratories": [laboratory],
  "/course-offerings": [offering], "/working-days": [day], "/laboratory-availability-blocks": [],
};

describe("Master Data business-key CSV export", () => {
  it("exports Course department and laboratory business keys without technical metadata", () => {
    const [row] = serializeMasterDataExport(masterConfigs.courses, [course], lookups);
    expect(row).toMatchObject({ course_code: "CS301", offering_department_code: "CSE", eligible_laboratory_codes: "CSE-LAB-01", preferred_laboratory_code: "CSE-LAB-01", is_active: "TRUE" });
    expect(row).not.toHaveProperty("offering_department_id");
    expect(row).not.toHaveProperty("default_laboratory_id");
    expect(row).not.toHaveProperty("id");
    expect(row).not.toHaveProperty("created_at");
    expect(row).not.toHaveProperty("updated_at");
    expect(row).toMatchObject({ grouping_mode: "GROUPED", default_group_count: 2, session_duration: 2, sessions_per_week: 2, venue_requirement: "LABORATORY_ONLY" });
  });

  it("exports readable Section, Faculty, Course Offering, allocation, and classroom assignment keys", () => {
    expect(serializeMasterDataExport(masterConfigs.sections, [section], lookups)[0]).toMatchObject({ program_code: "CSE-UG", academic_term_code: "2026-27 | I-I", primary_classroom_number: "3204" });
    expect(serializeMasterDataExport(masterConfigs.faculty, [faculty], lookups)[0]).toMatchObject({ faculty_code: "VCE042", department_code: "CSE" });
    const offeringExport = serializeMasterDataExport(masterConfigs["course-offerings"], [offering], lookups)[0];
    expect(offeringExport).toMatchObject({ course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I" });
    expect(offeringExport).not.toHaveProperty("is_common_theory"); expect(offeringExport).not.toHaveProperty("common_theory_group_code");
    expect(serializeMasterDataExport(masterConfigs["theory-allocations"], [{ id: "allocation-id", course_offering_id: ids.offering, faculty_id: ids.faculty, is_active: true }], lookups)[0]).toMatchObject({ course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", faculty_code: "VCE042" });
    expect(serializeMasterDataExport(masterConfigs["classroom-assignments"], [{ id: "assignment-id", section_id: ids.section, classroom_id: ids.classroom, academic_term_id: ids.term, is_primary: true, is_active: true }], lookups)[0]).toMatchObject({ section_code: "CSE-A", academic_term_code: "2026-27 | I-I", classroom_number: "3204" });
  });

  it("exports editable combined teaching groups with section codes and no UUIDs", () => {
    const secondSection = { ...section, id: "section-b", section_code: "CSE-B" };
    const secondOffering = { ...offering, id: "offering-b", section_id: secondSection.id };
    const row = { id: "group-id", academic_term_id: ids.term, group_code: "DS-CSE-AB", group_name: "Data Structures A+B", course_id: ids.course, faculty_id: ids.faculty, preferred_classroom_id: ids.classroom, preferred_laboratory_id: null, course_offering_ids: [ids.offering, "offering-b"], is_active: true };
    const [exported] = serializeMasterDataExport(masterConfigs["combined-teaching-groups"], [row], { ...lookups, "/sections": [section, secondSection], "/course-offerings": [offering, secondOffering] });
    expect(exported).toMatchObject({ academic_term_code: "2026-27 | I-I", group_code: "DS-CSE-AB", course_code: "CS301", section_codes: "CSE-A|CSE-B", faculty_code: "VCE042", classroom_number: "3204" });
    expect(Object.keys(exported).some((key) => key.endsWith("_id"))).toBe(false);
  });

  it("exports generic Resource Availability with readable resource, term, and day values", () => {
    const [row] = resourceAvailabilityExportRows("CLASSROOM", classroom, term, "EXCEPT_BLOCKED", [{ id: "slot-id", working_day_id: ids.day, period_number: 2, availability_type: "BLOCKED", is_active: true }], [day]);
    expect(row).toEqual({ resource_type: "CLASSROOM", resource_code: "3204", academic_term_code: "2026-27 | I-I", availability_mode: "EXCEPT_BLOCKED", blocked_periods: "Mon:P2", allowed_periods: "" });
    expect(Object.keys(row).some((key) => key.endsWith("_id"))).toBe(false);
  });

  it("generates no technical or raw foreign-key headers for any normal Master Data export", () => {
    for (const config of Object.values(masterConfigs)) {
      const headers = csvTemplateColumns(config);
      expect(headers, config.slug).not.toContain("id");
      expect(headers.some((header) => header.endsWith("_id")), config.slug).toBe(false);
      expect(headers, config.slug).not.toEqual(expect.arrayContaining(["created_at", "updated_at", "deleted_at", "created_by", "updated_by"]));
    }
  });

  it("never emits a UUID when readable metadata exists", () => {
    const rows = [
      ...serializeMasterDataExport(masterConfigs.courses, [course], lookups),
      ...serializeMasterDataExport(masterConfigs["course-offerings"], [offering], lookups),
      ...serializeMasterDataExport(masterConfigs.sections, [section], lookups),
    ];
    expect(JSON.stringify(rows)).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}/i);
  });

  it("round-trips a Course export through its readable-key import resolver", () => {
    const [exported] = serializeMasterDataExport(masterConfigs.courses, [course], lookups);
    const source = Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")]));
    const resolved = resolveCsvImportRow(masterConfigs.courses, source, lookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ offering_department_id: ids.department, eligible_laboratory_ids: [ids.laboratory], default_laboratory_id: ids.laboratory, course_code: "CS301", is_active: true });
  });

  it("round-trips laboratory capacity concurrency without UUID columns", () => {
    const shared = { ...laboratory, capacity: 60, concurrent_usage_mode: "CAPACITY_SHARED", availability_mode: "ALL_PERIODS", is_shareable_across_departments: true };
    const [exported] = serializeMasterDataExport(masterConfigs.laboratories, [shared], lookups);
    expect(exported).toMatchObject({ laboratory_code: "CSE-LAB-01", capacity: 60, concurrent_usage_mode: "CAPACITY_SHARED", department_code: "CSE" });
    expect(Object.keys(exported).some((key) => key.endsWith("_id"))).toBe(false);
    const resolved = resolveCsvImportRow(masterConfigs.laboratories, Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")])), lookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ owning_department_id: ids.department, capacity: 60, concurrent_usage_mode: "CAPACITY_SHARED" });
  });

  it("round-trips an offering laboratory override without exposing its ID", () => {
    const preferred = { ...offering, laboratory_selection_mode: "PREFERRED", laboratory_override_id: ids.laboratory };
    const [exported] = serializeMasterDataExport(masterConfigs["course-offerings"], [preferred], lookups);
    expect(exported).toMatchObject({ laboratory_selection_mode: "PREFERRED", laboratory_code: "CSE-LAB-01" });
    expect(Object.keys(exported).some((key) => key.endsWith("_id"))).toBe(false);
    const resolved = resolveCsvImportRow(masterConfigs["course-offerings"], Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")])), lookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ laboratory_selection_mode: "PREFERRED", laboratory_override_id: ids.laboratory });
  });

  it("round-trips a readable restricted offering laboratory set", () => {
    const second = { id: "lab-2", laboratory_code: "PHY-2", laboratory_name: "Physics Lab 2", is_active: true };
    const restrictedCourse = { ...course, eligible_laboratory_ids: [ids.laboratory, second.id] };
    const restricted = { ...offering, laboratory_selection_mode: "RESTRICTED", laboratory_override_id: null, allowed_laboratory_ids: [ids.laboratory, second.id] };
    const restrictedLookups = { ...lookups, "/courses": [restrictedCourse], "/laboratories": [...lookups["/laboratories"], second], "/course-offerings": [restricted] };
    const [exported] = serializeMasterDataExport(masterConfigs["course-offerings"], [restricted], restrictedLookups);
    expect(exported).toMatchObject({ laboratory_selection_mode: "RESTRICTED", laboratory_code: "", allowed_laboratory_codes: "CSE-LAB-01|PHY-2" });
    expect(Object.keys(exported).some((key) => key.endsWith("_id"))).toBe(false);
    const resolved = resolveCsvImportRow(masterConfigs["course-offerings"], Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")])), restrictedLookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ laboratory_selection_mode: "RESTRICTED", laboratory_override_id: null, allowed_laboratory_ids: [ids.laboratory, second.id] });
  });

  it("leaves laboratory fields blank for a classroom-only offering and accepts that export on import", () => {
    const classroomCourse = { ...course, id: "theory-course", course_code: "A9001", course_name: "Matrices and Calculus", course_type: "THEORY", venue_requirement: "CLASSROOM_ONLY", eligible_laboratory_ids: [], default_laboratory_id: null };
    const classroomOffering = { ...offering, id: "theory-offering", course_id: classroomCourse.id, laboratory_selection_mode: "AUTO", laboratory_override_id: null };
    const classroomLookups = { ...lookups, "/courses": [course, classroomCourse], "/course-offerings": [offering, classroomOffering] };
    const [exported] = serializeMasterDataExport(masterConfigs["course-offerings"], [classroomOffering], classroomLookups);
    expect(exported).toMatchObject({ laboratory_selection_mode: "", laboratory_code: "" });
    const resolved = resolveCsvImportRow(masterConfigs["course-offerings"], Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")])), classroomLookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ laboratory_selection_mode: "AUTO", laboratory_override_id: null });
  });

  it("round-trips a grouped classroom practical without a laboratory key", () => {
    const practical = { ...course, id: "practical", course_code: "CCDT", course_name: "Community Centered Design Thinking", course_type: "PRACTICAL", weekly_periods: 3, grouping_mode: "GROUPED", default_group_count: 2, session_duration: 3, sessions_per_week: 1, venue_requirement: "CLASSROOM_ONLY", eligible_laboratory_ids: [], default_laboratory_id: null };
    const [exported] = serializeMasterDataExport(masterConfigs.courses, [practical], lookups);
    expect(exported).toMatchObject({ course_code: "CCDT", grouping_mode: "GROUPED", session_duration: 3, sessions_per_week: 1, venue_requirement: "CLASSROOM_ONLY", eligible_laboratory_codes: "", preferred_laboratory_code: "" });
    const resolved = resolveCsvImportRow(masterConfigs.courses, Object.fromEntries(Object.entries(exported).map(([key, value]) => [key, String(value ?? "")])), lookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ course_type: "PRACTICAL", default_laboratory_id: null, default_group_count: 2 });
  });

  it("fails clearly instead of falling back to an unresolved UUID", () => {
    expect(() => serializeMasterDataExport(masterConfigs.courses, [course], { ...lookups, "/departments": [] })).toThrow(/export stopped rather than exposing/);
  });
});
