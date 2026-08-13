import { describe, expect, it } from "vitest";
import { masterConfigs } from "@/lib/master-data-config";
import { csvTemplateColumns, resolveCsvImportRow } from "@/lib/csv-import-resolution";
import type { MasterRecord } from "@/lib/master-data-api";

const term = { id: "term-1", academic_year: "2026-27", term_name: "I-I", is_active: true, is_current: true };
const department = { id: "department-1", department_code: "CSE", department_name: "Computer Science", is_active: true };
const program = { id: "program-1", program_code: "CSE-UG", program_name: "B.Tech CSE", department_id: department.id, is_active: true };
const section = { id: "section-1", section_code: "CSE-A", section_name: "A", academic_term_id: term.id, program_id: program.id, is_active: true };
const faculty = { id: "faculty-1", faculty_code: "VCE042", full_name: "Dr. R. Kumar", is_active: true };
const course = { id: "course-1", course_code: "CS301", course_name: "Operating Systems", is_active: true };
const classroom = { id: "classroom-1", room_number: "3204", room_name: "CSE Block", is_active: true };
const laboratory = { id: "laboratory-1", laboratory_code: "CSE-LAB-01", laboratory_name: "Programming Lab", is_active: true };
const workingDay = { id: "day-1", day_name: "Monday", is_active: true, is_working_day: true };
const offering = { id: "offering-1", course_id: course.id, section_id: section.id, academic_term_id: term.id, is_active: true };
const sectionB = { ...section, id: "section-2", section_code: "CSE-B" };
const offeringB = { ...offering, id: "offering-2", section_id: sectionB.id };

const lookups: Record<string, MasterRecord[]> = {
  "/academic-terms": [term], "/departments": [department], "/programs": [program], "/sections": [section],
  "/faculty": [faculty], "/courses": [course], "/classrooms": [classroom], "/laboratories": [laboratory],
  "/working-days": [workingDay], "/course-offerings": [offering],
};

describe("readable CSV import resolution", () => {
  it("resolves department and program codes to internal IDs", () => {
    const programRow = resolveCsvImportRow(masterConfigs.programs, { department_code: "CSE", program_code: "CSE-UG", program_name: "B.Tech CSE", degree_type: "UG", duration_years: "4" }, lookups);
    expect(programRow.errors).toEqual([]);
    expect(programRow.payload.department_id).toBe(department.id);

    const sectionRow = resolveCsvImportRow(masterConfigs.sections, { program_code: "CSE-UG", academic_term_code: "2026-27 | I-I", section_name: "A", student_strength: "72" }, lookups);
    expect(sectionRow.payload.program_id).toBe(program.id);
  });

  it("resolves a section code within its academic term", () => {
    const otherTerm = { ...term, id: "term-2", term_name: "II-I" };
    const otherSection = { ...section, id: "section-2", academic_term_id: otherTerm.id };
    const row = resolveCsvImportRow(masterConfigs["student-batches"], { section_code: "CSE-A", academic_term_code: "2026-27 | I-I", batch_name: "A1", sequence_number: "1", roll_number_start: "1", roll_number_end: "72", student_count: "72" }, { ...lookups, "/academic-terms": [term, otherTerm], "/sections": [section, otherSection] });
    expect(row.errors).toEqual([]);
    expect(row.payload.section_id).toBe(section.id);
  });

  it("maps the readable student_group_name header to the internal batch_name field", () => {
    const row = resolveCsvImportRow(masterConfigs["student-batches"], { section_code: "CSE-A", academic_term_code: "2026-27 | I-I", student_group_name: "A1", sequence_number: "1", roll_number_start: "1", roll_number_end: "72", student_count: "72", is_active: "TRUE" }, lookups);
    expect(row.errors).toEqual([]);
    expect(row.payload).toMatchObject({ section_id: section.id, batch_name: "A1", is_active: true });
  });

  it("resolves faculty, course, classroom, laboratory, and working-day keys", () => {
    const allocation = resolveCsvImportRow(masterConfigs["theory-allocations"], { course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", faculty_code: "VCE042" }, lookups);
    expect(allocation.payload).toMatchObject({ course_offering_id: offering.id, faculty_id: faculty.id });

    const assignment = resolveCsvImportRow(masterConfigs["classroom-assignments"], { section_code: "CSE-A", academic_term_code: "2026-27 | I-I", classroom_number: "3204", is_primary: "true" }, lookups);
    expect(assignment.payload.classroom_id).toBe(classroom.id);

    const block = resolveCsvImportRow(masterConfigs["lab-availability-blocks"], { laboratory_code: "CSE-LAB-01", academic_term_code: "2026-27 | I-I", day_name: "Monday", period_number: "2" }, lookups);
    expect(block.payload).toMatchObject({ laboratory_id: laboratory.id, working_day_id: workingDay.id });
  });

  it("reports unknown, inactive, and ambiguous business keys at row level", () => {
    const unknown = resolveCsvImportRow(masterConfigs.programs, { department_code: "BAD", program_code: "BAD-UG", program_name: "Bad", degree_type: "UG", duration_years: "4" }, lookups);
    expect(unknown.errors.join(" ")).toContain("Unknown department reference 'BAD'");

    const ambiguous = resolveCsvImportRow(masterConfigs.programs, { department_code: "CSE", program_code: "CSE-UG", program_name: "B.Tech CSE", degree_type: "UG", duration_years: "4" }, { ...lookups, "/departments": [department, { ...department, id: "department-2" }] });
    expect(ambiguous.errors.join(" ")).toContain("Ambiguous department reference");

    const inactive = resolveCsvImportRow(masterConfigs.programs, { department_code: "CSE", program_code: "CSE-UG", program_name: "B.Tech CSE", degree_type: "UG", duration_years: "4" }, { ...lookups, "/departments": [{ ...department, is_active: false }] });
    expect(inactive.errors.join(" ")).toContain("is inactive");
  });

  it("generates UUID-free templates for every supported module", () => {
    for (const config of Object.values(masterConfigs)) {
      const columns = csvTemplateColumns(config);
      expect(columns, config.slug).not.toContain("id");
      expect(columns.some((column) => column.endsWith("_id")), config.slug).toBe(false);
      expect(columns, config.slug).not.toContain("user_id");
    }
    expect(csvTemplateColumns(masterConfigs.faculty)).not.toContain("user_id");
    expect(csvTemplateColumns(masterConfigs.courses)).toContain("offering_department_code");
    expect(csvTemplateColumns(masterConfigs.courses)).toEqual(expect.arrayContaining(["eligible_laboratory_codes", "preferred_laboratory_code"]));
    expect(csvTemplateColumns(masterConfigs.courses)).not.toContain("offering_department_id");
    expect(csvTemplateColumns(masterConfigs["course-offerings"])).toEqual(expect.arrayContaining(["course_code", "section_code", "academic_term_code", "laboratory_selection_mode", "laboratory_code", "allowed_laboratory_codes"]));
    expect(csvTemplateColumns(masterConfigs["course-offerings"])).not.toEqual(expect.arrayContaining(["is_common_theory", "common_theory_group_code"]));
    expect(csvTemplateColumns(masterConfigs["batch-configurations"])).toContain("number_of_groups");
    expect(csvTemplateColumns(masterConfigs["batch-configurations"])).not.toContain("number_of_batches");
    expect(csvTemplateColumns(masterConfigs["student-batches"])).toContain("student_group_name");
    expect(csvTemplateColumns(masterConfigs["student-batches"])).not.toContain("batch_name");
    expect(csvTemplateColumns(masterConfigs.laboratories)).toEqual(expect.arrayContaining(["availability_mode", "academic_term_code", "blocked_periods", "allowed_periods"]));
  });

  it("resolves compact blocked and selected laboratory periods without UUID columns", () => {
    const blocked = resolveCsvImportRow(masterConfigs.laboratories, { laboratory_code: "CSE-LAB-02", laboratory_name: "Networks Lab", room_number: "3102", department_code: "CSE", is_shareable_across_departments: "true", availability_mode: "EXCEPT_BLOCKED", blocked_periods: "Mon:P1|Mon:P2" }, lookups);
    expect(blocked.errors).toEqual([]);
    expect(blocked.references.map((item) => item.resolvedLabel)).toEqual(expect.arrayContaining(["Monday · P1", "Monday · P2"]));
    expect(blocked.payload).toMatchObject({ availability_mode: "EXCEPT_BLOCKED", owning_department_id: department.id });
    expect(blocked.payload).not.toHaveProperty("working_day_id");

    const selected = resolveCsvImportRow(masterConfigs.laboratories, { laboratory_code: "CSE-LAB-03", laboratory_name: "AI Lab", room_number: "3103", department_code: "CSE", is_shareable_across_departments: "true", availability_mode: "ONLY_SELECTED", allowed_periods: "Mon:P5" }, lookups);
    expect(selected.errors).toEqual([]);
    expect(selected.references.some((item) => item.resolvedLabel === "Monday · P5")).toBe(true);
  });

  it("rejects invalid or empty selected-period CSV configurations", () => {
    const empty = resolveCsvImportRow(masterConfigs.laboratories, { laboratory_code: "L1", laboratory_name: "Lab", room_number: "1", department_code: "CSE", availability_mode: "ONLY_SELECTED" }, lookups);
    expect(empty.errors.join(" ")).toContain("requires at least one allowed period");
    const unknown = resolveCsvImportRow(masterConfigs.laboratories, { laboratory_code: "L2", laboratory_name: "Lab", room_number: "2", department_code: "CSE", availability_mode: "EXCEPT_BLOCKED", blocked_periods: "Sunday:P1" }, lookups);
    expect(unknown.errors.join(" ")).toContain("Unknown working day");
  });

  it("accepts arbitrary positive laboratory group counts in CSV payloads", () => {
    const configuration = resolveCsvImportRow(masterConfigs["batch-configurations"], { course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", number_of_groups: "6", group_naming_pattern: "{section}{sequence}" }, { ...lookups, "/laboratory-batch-configurations": [] });
    expect(configuration.errors).toEqual([]);
    expect(configuration.payload.number_of_groups).toBe(6);
  });

  it("keeps readable source values out of the final UUID-based API payload", () => {
    const row = resolveCsvImportRow(masterConfigs["course-offerings"], { course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", is_mandatory: "true" }, lookups);
    expect(row.errors).toEqual([]);
    expect(row.payload).toMatchObject({ course_id: course.id, section_id: section.id, academic_term_id: term.id });
    expect(row.payload).not.toHaveProperty("course_code");
    expect(row.payload).not.toHaveProperty("section_code");
    expect(row.payload).not.toHaveProperty("academic_term_code");
  });

  it("resolves a restricted offering laboratory subset and rejects unknown or duplicate codes", () => {
    const laboratory2 = { id: "lab-uuid-2", laboratory_code: "PHY-2", laboratory_name: "Physics Lab 2", is_active: true };
    const restrictedCourse = { ...course, venue_requirement: "LABORATORY_ONLY", eligible_laboratory_ids: [laboratory.id, laboratory2.id] };
    const restrictedLookups = { ...lookups, "/courses": [restrictedCourse], "/laboratories": [laboratory, laboratory2] };
    const source = { course_code: "CS301", section_code: "CSE-A", academic_term_code: "2026-27 | I-I", laboratory_selection_mode: "RESTRICTED", allowed_laboratory_codes: "CSE-LAB-01|PHY-2", is_mandatory: "true" };
    const resolved = resolveCsvImportRow(masterConfigs["course-offerings"], source, restrictedLookups);
    expect(resolved.errors).toEqual([]);
    expect(resolved.payload).toMatchObject({ laboratory_selection_mode: "RESTRICTED", laboratory_override_id: null, allowed_laboratory_ids: [laboratory.id, laboratory2.id] });
    expect(resolved.payload).not.toHaveProperty("allowed_laboratory_codes");
    const unknown = resolveCsvImportRow(masterConfigs["course-offerings"], { ...source, allowed_laboratory_codes: "UNKNOWN" }, restrictedLookups);
    expect(unknown.errors.join(" ")).toContain("Unknown laboratory");
    const duplicate = resolveCsvImportRow(masterConfigs["course-offerings"], { ...source, allowed_laboratory_codes: "PHY-2|PHY-2" }, restrictedLookups);
    expect(duplicate.errors.join(" ")).toContain("Duplicate laboratory code");
  });

  it("resolves a combined teaching membership from deterministic section business keys", () => {
    const row = resolveCsvImportRow(masterConfigs["combined-teaching-groups"], { academic_term_code: "2026-27 | I-I", group_code: "DS-CSE-AB", group_name: "Data Structures A+B", course_code: "CS301", section_codes: "CSE-A|CSE-B", faculty_code: "VCE042", classroom_number: "3204" }, { ...lookups, "/sections": [section, sectionB], "/course-offerings": [offering, offeringB] });
    expect(row.errors).toEqual([]);
    expect(row.payload).toMatchObject({ academic_term_id: term.id, course_id: course.id, faculty_id: faculty.id, preferred_classroom_id: classroom.id, course_offering_ids: [offering.id, offeringB.id] });
    expect(row.payload).not.toHaveProperty("section_codes");
    expect(csvTemplateColumns(masterConfigs["combined-teaching-groups"])).toEqual(expect.arrayContaining(["academic_term_code", "course_code", "section_codes", "faculty_code", "classroom_number"]));
    expect(csvTemplateColumns(masterConfigs["combined-teaching-groups"]).some((column) => column.endsWith("_id"))).toBe(false);
  });
});
