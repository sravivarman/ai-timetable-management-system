import { csvTemplateColumns, importLookupEndpoints, relationSpec, type ImportLookupRecords } from "@/lib/csv-import-resolution";
import { laboratoryAvailabilityExportRows } from "@/lib/laboratory-availability-export";
import type { MasterRecord } from "@/lib/master-data-api";
import type { MasterConfig, MasterField } from "@/lib/master-data-config";
import { isLaboratoryCapableCourse } from "@/lib/course-offering-laboratories";

export function businessExportLookupEndpoints(config: MasterConfig): string[] {
  return importLookupEndpoints(config);
}

export function serializeMasterDataExport(
  config: MasterConfig,
  records: MasterRecord[],
  lookups: ImportLookupRecords,
): Record<string, unknown>[] {
  const headers = csvTemplateColumns(config);
  if (config.slug === "laboratories") {
    const rows = laboratoryAvailabilityExportRows(
      records,
      lookups["/departments"] ?? [],
      lookups["/academic-terms"] ?? [],
      lookups["/working-days"] ?? [],
      lookups["/laboratory-availability-blocks"] ?? [],
    );
    return normalizeRows(headers, rows);
  }

  return records.map((record, index) => {
    const values: Record<string, unknown> = {};
    const offeringCourse = config.slug === "course-offerings" ? requireRecord(lookups["/courses"] ?? [], record.course_id, "course", `${config.singular} row ${index + 1}`) : undefined;
    for (const field of config.fields) {
      if (offeringCourse && !isLaboratoryCapableCourse(offeringCourse) && ["laboratory_selection_mode", "laboratory_override_id", "allowed_laboratory_ids"].includes(field.name)) {
        values[field.name === "laboratory_override_id" ? "laboratory_code" : field.name === "allowed_laboratory_ids" ? "allowed_laboratory_codes" : field.name] = "";
        continue;
      }
      const relation = relationSpec(field);
      if (relation) {
        const resolved = exportRelation(field, record[field.name], lookups, `${config.singular} row ${index + 1}`);
        for (const [column, value] of Object.entries(resolved)) assignConsistently(values, column, value, `${config.singular} row ${index + 1}`);
      } else {
        const column = config.slug === "student-batches" && field.name === "batch_name" ? "student_group_name" : field.name;
        values[column] = record[field.name];
      }
    }
    if (headers.includes("is_active")) values.is_active = record.is_active;
    return normalizeRow(headers, values);
  });
}

function exportRelation(field: MasterField, identifier: unknown, lookups: ImportLookupRecords, context: string): Record<string, unknown> {
  const spec = relationSpec(field)!;
  if (identifier == null || identifier === "") return Object.fromEntries(spec.columns.map((column) => [column, ""]));
  if (["eligible_laboratory_ids", "allowed_laboratory_ids"].includes(field.name)) {
    const identifiers = Array.isArray(identifier) ? identifier : [];
    const codes = identifiers.map((value) => requiredValue(requireRecord(lookups["/laboratories"] ?? [], value, "laboratory", context), "laboratory_code", "laboratory", context));
    return { [field.name === "allowed_laboratory_ids" ? "allowed_laboratory_codes" : "eligible_laboratory_codes"]: codes.join("|") };
  }
  if (field.name === "course_offering_ids") {
    const identifiers = Array.isArray(identifier) ? identifier : [];
    const sectionCodes = identifiers.map((value) => {
      const offering = requireRecord(lookups["/course-offerings"] ?? [], value, "course offering", context);
      const section = requireRecord(lookups["/sections"] ?? [], offering.section_id, "section", context);
      return requiredValue(section, "section_code", "section", context);
    }).sort();
    return { section_codes: sectionCodes.join("|") };
  }
  const record = requireRecord(lookups[spec.endpoint] ?? [], identifier, field.label, context);

  if (field.name === "course_offering_id") return offeringKeys(record, lookups, context);
  if (field.name === "laboratory_batch_configuration_id") {
    const offering = requireRecord(lookups["/course-offerings"] ?? [], record.course_offering_id, "course offering", context);
    return offeringKeys(offering, lookups, context);
  }
  if (field.name === "academic_term_id") return { academic_term_code: academicTermCode(record, context) };
  if (field.name === "section_id") return sectionKeys(record, lookups, context);

  const simple: Record<string, { column: string; key: string }> = {
    department_id: { column: "department_code", key: "department_code" },
    offering_department_id: { column: "offering_department_code", key: "department_code" },
    owning_department_id: { column: "department_code", key: "department_code" },
    program_id: { column: "program_code", key: "program_code" },
    faculty_id: { column: "faculty_code", key: "faculty_code" },
    required_with_main_faculty_id: { column: "required_main_faculty_code", key: "faculty_code" },
    course_id: { column: "course_code", key: "course_code" },
    classroom_id: { column: "classroom_number", key: "room_number" },
    preferred_classroom_id: { column: "classroom_number", key: "room_number" },
    primary_classroom_id: { column: "primary_classroom_number", key: "room_number" },
    laboratory_id: { column: "laboratory_code", key: "laboratory_code" },
    laboratory_override_id: { column: "laboratory_code", key: "laboratory_code" },
    preferred_laboratory_id: { column: "laboratory_code", key: "laboratory_code" },
    default_laboratory_id: { column: "preferred_laboratory_code", key: "laboratory_code" },
    working_day_id: { column: "day_name", key: "day_name" },
    student_batch_id: { column: "student_group_name", key: "batch_name" },
    batch_id: { column: "student_group_name", key: "batch_name" },
  };
  const definition = simple[field.name];
  if (!definition) throw new Error(`${context}: no readable export key is configured for ${field.name}.`);
  const value = record[definition.key];
  if (value == null || value === "") throw new Error(`${context}: ${field.label} has no ${definition.key}; export stopped rather than exposing its internal ID.`);
  return { [definition.column]: value };
}

function offeringKeys(offering: MasterRecord, lookups: ImportLookupRecords, context: string) {
  const course = requireRecord(lookups["/courses"] ?? [], offering.course_id, "course", context);
  const section = requireRecord(lookups["/sections"] ?? [], offering.section_id, "section", context);
  const term = requireRecord(lookups["/academic-terms"] ?? [], offering.academic_term_id, "academic term", context);
  const keys = sectionKeys(section, lookups, context);
  const termCode = academicTermCode(term, context);
  if (keys.academic_term_code !== termCode) throw new Error(`${context}: the course offering and section reference different academic terms.`);
  return { course_code: requiredValue(course, "course_code", "course", context), section_code: keys.section_code, academic_term_code: termCode };
}

function sectionKeys(section: MasterRecord, lookups: ImportLookupRecords, context: string) {
  const term = requireRecord(lookups["/academic-terms"] ?? [], section.academic_term_id, "section academic term", context);
  return { section_code: requiredValue(section, "section_code", "section", context), academic_term_code: academicTermCode(term, context) };
}

function academicTermCode(term: MasterRecord, context: string) {
  return `${requiredValue(term, "academic_year", "academic term", context)} | ${requiredValue(term, "term_name", "academic term", context)}`;
}

function requireRecord(records: MasterRecord[], identifier: unknown, label: string, context: string): MasterRecord {
  const matches = records.filter((record) => record.id === String(identifier));
  if (matches.length !== 1) throw new Error(`${context}: ${label} metadata could not be resolved; export stopped rather than exposing '${String(identifier)}'.`);
  return matches[0];
}

function requiredValue(record: MasterRecord, key: string, label: string, context: string) {
  const value = record[key];
  if (value == null || value === "") throw new Error(`${context}: ${label} has no ${key}.`);
  return String(value);
}

function assignConsistently(target: Record<string, unknown>, key: string, value: unknown, context: string) {
  const current = target[key];
  if (current != null && current !== "" && value != null && value !== "" && String(current) !== String(value)) {
    throw new Error(`${context}: conflicting readable values were resolved for ${key}.`);
  }
  if (current == null || current === "" || value !== "") target[key] = value;
}

function normalizeRows(headers: string[], rows: Record<string, unknown>[]) {
  return rows.map((row) => normalizeRow(headers, row));
}

function normalizeRow(headers: string[], values: Record<string, unknown>) {
  return Object.fromEntries(headers.map((header) => [header, canonicalValue(values[header])]));
}

function canonicalValue(value: unknown): unknown {
  if (value == null) return "";
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  if (Array.isArray(value)) return value.map(String).join("|");
  return value;
}
