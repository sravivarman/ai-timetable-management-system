import { coerceCsvRow } from "@/components/master-record-form";
import type { MasterConfig, MasterField } from "@/lib/master-data-config";
import type { MasterRecord } from "@/lib/master-data-api";
import { readableRecordLabel } from "@/lib/readable-labels";
import { resolveLaboratoryAvailabilityCsv } from "@/lib/laboratory-availability-csv";
import { normalizeOfferingLaboratoryPayload } from "@/lib/course-offering-laboratories";

export type ImportLookupRecords = Record<string, MasterRecord[]>;
export type ImportReferenceResolution = {
  targetField: string;
  sourceColumns: string[];
  original: string;
  resolvedLabel?: string;
  error?: string;
};
export type ResolvedImportRow = {
  source: Record<string, string>;
  internalRow: Record<string, string>;
  payload: Record<string, unknown>;
  references: ImportReferenceResolution[];
  errors: string[];
};

export type RelationSpec = { columns: string[]; endpoint: string };

const naturalKeys: Record<string, string[]> = {
  "academic-terms": ["academic_year", "term_name"],
  departments: ["department_code"],
  programs: ["program_code"],
  sections: ["program_id", "academic_term_id", "section_name"],
  faculty: ["faculty_code"],
  courses: ["course_code"],
  classrooms: ["room_number"],
  laboratories: ["laboratory_code"],
  "working-days": ["day_name"],
  "period-timings": ["schedule_type", "sequence_number"],
  "faculty-availability": ["faculty_id", "academic_term_id", "day_of_week", "period_number"],
  "faculty-scheduling-policies": ["faculty_id", "academic_term_id"],
  "course-offerings": ["course_id", "section_id", "academic_term_id"],
  "combined-teaching-groups": ["academic_term_id", "group_code"],
  "theory-allocations": ["course_offering_id"],
  "laboratory-allocations": ["course_offering_id", "faculty_id", "role_type"],
  "student-batches": ["section_id", "batch_name"],
  "batch-configurations": ["course_offering_id"],
  rotations: ["laboratory_batch_configuration_id", "rotation_code"],
  "classroom-assignments": ["section_id", "academic_term_id"],
  "lab-availability-blocks": ["laboratory_id", "academic_term_id", "working_day_id", "period_number"],
};

export function csvTemplateColumns(config: MasterConfig): string[] {
  const columns: string[] = [];
  for (const field of config.fields) {
    const relation = relationSpec(field);
    const fieldColumns = config.slug === "student-batches" && field.name === "batch_name" ? ["student_group_name"] : relation?.columns ?? [field.name];
    for (const column of fieldColumns) if (!columns.includes(column) && !column.endsWith("_id") && column !== "id" && column !== "user_id") columns.push(column);
  }
  if (config.slug === "laboratories") columns.push("academic_term_code", "blocked_periods", "allowed_periods");
  if (!columns.includes("is_active")) columns.push("is_active");
  return columns;
}

export function requiredCsvColumns(config: MasterConfig): string[] {
  const required: string[] = [];
  for (const field of config.fields.filter((item) => item.required)) {
    for (const column of relationSpec(field)?.columns ?? [field.name]) if (!required.includes(column)) required.push(column);
  }
  return required;
}

export function importLookupEndpoints(config: MasterConfig): string[] {
  const endpoints = new Set<string>([config.endpoint]);
  for (const field of config.fields) if (field.lookup) endpoints.add(field.lookup.endpoint);
  if ([...config.fields].some((field) => ["section_id", "course_offering_id", "course_offering_ids", "laboratory_batch_configuration_id"].includes(field.name))) endpoints.add("/academic-terms");
  if ([...config.fields].some((field) => ["course_offering_id", "course_offering_ids", "laboratory_batch_configuration_id"].includes(field.name))) {
    endpoints.add("/course-offerings"); endpoints.add("/courses"); endpoints.add("/sections");
  }
  if (config.fields.some((field) => field.name === "laboratory_batch_configuration_id")) endpoints.add("/laboratory-batch-configurations");
  if (config.slug === "laboratories") { endpoints.add("/academic-terms"); endpoints.add("/working-days"); endpoints.add("/laboratory-availability-blocks"); }
  return [...endpoints].sort();
}

export function resolveCsvImportRow(config: MasterConfig, source: Record<string, string>, lookups: ImportLookupRecords): ResolvedImportRow {
  const input: Record<string, string> = { ...source };
  if (config.slug === "student-batches" && !input.batch_name && source.student_group_name) input.batch_name = source.student_group_name;
  if (!input.offering_department_code && source.department_code) input.offering_department_code = source.department_code;
  if (!input.preferred_laboratory_code && source.default_laboratory_code) input.preferred_laboratory_code = source.default_laboratory_code;
  const internalRow = { ...input };
  const references: ImportReferenceResolution[] = [];
  for (const field of config.fields) {
    const spec = relationSpec(field);
    if (!spec) continue;
    const original = spec.columns.map((column) => input[column]?.trim()).filter(Boolean).join(" | ");
    if (!original) { internalRow[field.name] = ""; continue; }
    if (["eligible_laboratory_ids", "allowed_laboratory_ids"].includes(field.name)) {
      const column = field.name === "allowed_laboratory_ids" ? "allowed_laboratory_codes" : "eligible_laboratory_codes";
      const codes = input[column].split(/[|;]/).map((value) => value.trim()).filter(Boolean);
      const duplicateCodes = codes.filter((code, index) => codes.findIndex((value) => normalize(value) === normalize(code)) !== index);
      if (duplicateCodes.length) {
        references.push({ targetField: field.name, sourceColumns: spec.columns, original, error: `Duplicate laboratory code '${duplicateCodes[0]}'.` });
        continue;
      }
      const matches = codes.map((laboratory_code) => selectReference(lookups[spec.endpoint] ?? [], (record) => normalize(record.laboratory_code) === normalize(laboratory_code), "laboratory", ["eligible_laboratory_codes"], { ...input, eligible_laboratory_codes: laboratory_code }));
      const errors = matches.flatMap((match) => match.error ? [match.error] : []);
      references.push({ targetField: field.name, sourceColumns: spec.columns, original, resolvedLabel: errors.length ? undefined : matches.map((match) => readableRecordLabel(spec.endpoint, match.record!)).join("; "), error: errors.length ? errors.join(" ") : undefined });
      if (!errors.length) internalRow[field.name] = matches.map((match) => match.record!.id).join("|");
      continue;
    }
    if (field.name === "course_offering_ids") {
      const sections = input.section_codes.split(/[|;]/).map((value) => value.trim()).filter(Boolean);
      const matches = sections.map((section_code) => resolveOffering({ ...input, section_code }, lookups, spec.endpoint));
      const errors = matches.flatMap((match) => match.error ? [match.error] : []);
      references.push({ targetField: field.name, sourceColumns: spec.columns, original, resolvedLabel: errors.length ? undefined : matches.map((match) => readableRecordLabel(spec.endpoint, match.record!)).join("; "), error: errors.length ? errors.join(" ") : undefined });
      if (!errors.length) internalRow[field.name] = matches.map((match) => match.record!.id).join("|");
      continue;
    }
    const match = resolveRelation(field, input, lookups);
    const reference: ImportReferenceResolution = { targetField: field.name, sourceColumns: spec.columns, original };
    if (match.error) reference.error = match.error;
    else if (match.record) {
      internalRow[field.name] = match.record.id;
      reference.resolvedLabel = readableRecordLabel(spec.endpoint, match.record);
    }
    references.push(reference);
  }
  const converted = coerceCsvRow(config, internalRow);
  if (["theory-allocations", "laboratory-allocations"].includes(config.slug)) {
    const offering = (lookups["/course-offerings"] ?? []).find((record) => record.id === String(converted.payload.course_offering_id ?? ""));
    const activity = offering && ["LABORATORY", "PRACTICAL"].includes(String(offering.course_type));
    if (offering && config.slug === "laboratory-allocations" && !activity) references.push({ targetField: "course_offering_id", sourceColumns: ["course_code", "section_code", "academic_term_code"], original: [input.course_code, input.section_code, input.academic_term_code].filter(Boolean).join(" | "), error: "Activity faculty allocations support only laboratory or practical course offerings." });
    if (offering && config.slug === "theory-allocations" && activity) references.push({ targetField: "course_offering_id", sourceColumns: ["course_code", "section_code", "academic_term_code"], original: [input.course_code, input.section_code, input.academic_term_code].filter(Boolean).join(" | "), error: "Use Activity Faculty Allocations for laboratory or practical course offerings." });
  }
  if (config.slug === "course-offerings") {
    const course = (lookups["/courses"] ?? []).find((record) => record.id === String(converted.payload.course_id ?? ""));
    if (course) normalizeOfferingLaboratoryPayload(converted.payload, course);
    const allowed = Array.isArray(converted.payload.allowed_laboratory_ids) ? converted.payload.allowed_laboratory_ids.map(String) : [];
    const eligible = new Set(Array.isArray(course?.eligible_laboratory_ids) ? course.eligible_laboratory_ids.map(String) : course?.default_laboratory_id ? [String(course.default_laboratory_id)] : []);
    for (const identifier of allowed) if (!eligible.has(identifier)) references.push({ targetField: "allowed_laboratory_ids", sourceColumns: ["allowed_laboratory_codes"], original: input.allowed_laboratory_codes ?? "", error: "Allowed laboratory is not eligible for the selected course." });
  }
  const active = parseOptionalBoolean(source.is_active);
  const availability = config.slug === "laboratories" ? resolveLaboratoryAvailabilityCsv(input, lookups) : undefined;
  return {
    source,
    internalRow,
    payload: active.value === undefined ? converted.payload : { ...converted.payload, is_active: active.value },
    references: [...references, ...(availability?.references ?? [])],
    errors: [...references.flatMap((item) => item.error ? [item.error] : []), ...Object.values(converted.errors), ...(active.error ? [active.error] : []), ...(availability?.errors ?? [])],
  };
}

export function addDuplicateCsvErrors(config: MasterConfig, rows: ResolvedImportRow[]): ResolvedImportRow[] {
  const groups = new Map<string, number[]>();
  rows.forEach((row, index) => {
    if (row.errors.length) return;
    const key = importBusinessKey(config, row.payload);
    if (key) groups.set(key, [...(groups.get(key) ?? []), index]);
  });
  const duplicateIndexes = new Set([...groups.values()].filter((indexes) => indexes.length > 1).flat());
  return rows.map((row, index) => duplicateIndexes.has(index) ? { ...row, errors: [...row.errors, "Duplicate business key appears more than once in this CSV file."] } : row);
}

export function findExistingImportRecord(config: MasterConfig, payload: Record<string, unknown>, records: MasterRecord[]): { record?: MasterRecord; error?: string } {
  const key = importBusinessKey(config, payload);
  if (!key) return {};
  const matches = records.filter((record) => importBusinessKey(config, record) === key);
  if (matches.length > 1) return { error: `Existing ${config.singular.toLowerCase()} records are ambiguous for this business key.` };
  return { record: matches[0] };
}

export function importBusinessKey(config: MasterConfig, payload: Record<string, unknown>): string | undefined {
  if (config.slug === "classroom-assignments") {
    const section = payload.section_id; const term = payload.academic_term_id;
    if (!section || !term) return undefined;
    if (payload.is_primary !== false) return `${comparable(section)}|${comparable(term)}|PRIMARY`;
    return [section, term, "ALTERNATIVE", payload.classroom_id, payload.effective_from, payload.effective_to].map(comparable).join("|");
  }
  const keys = naturalKeys[config.slug];
  if (!keys || keys.some((key) => payload[key] == null || payload[key] === "")) return undefined;
  return keys.map((key) => comparable(payload[key])).join("|");
}

export function relationSpec(field: MasterField): RelationSpec | undefined {
  if (!field.lookup) return undefined;
  const endpoint = field.lookup.endpoint;
  if (field.name === "course_offering_ids") return { endpoint, columns: ["section_codes"] };
  if (field.name === "eligible_laboratory_ids") return { endpoint, columns: ["eligible_laboratory_codes"] };
  if (field.name === "allowed_laboratory_ids") return { endpoint, columns: ["allowed_laboratory_codes"] };
  if (field.name === "course_offering_id" || field.name === "laboratory_batch_configuration_id") return { endpoint, columns: ["course_code", "section_code", "academic_term_code"] };
  if (field.name === "required_with_main_faculty_id") return { endpoint, columns: ["required_main_faculty_code"] };
  if (field.name === "primary_classroom_id") return { endpoint, columns: ["primary_classroom_number"] };
  if (field.name === "default_laboratory_id") return { endpoint, columns: ["preferred_laboratory_code"] };
  if (field.name === "laboratory_override_id") return { endpoint, columns: ["laboratory_code"] };
  const columns: Record<string, string[]> = {
    department_id: ["department_code"], offering_department_id: ["offering_department_code"], owning_department_id: ["department_code"],
    program_id: ["program_code"], academic_term_id: ["academic_term_code"], section_id: ["section_code", "academic_term_code"],
    faculty_id: ["faculty_code"], course_id: ["course_code"], classroom_id: ["classroom_number"], preferred_classroom_id: ["classroom_number"], laboratory_id: ["laboratory_code"], laboratory_override_id: ["laboratory_code"], preferred_laboratory_id: ["laboratory_code"],
    working_day_id: ["day_name"], student_batch_id: ["student_group_name"], batch_id: ["student_group_name"],
  };
  return { endpoint, columns: columns[field.name] ?? [field.name.replace(/_id$/, "_code")] };
}

function resolveRelation(field: MasterField, row: Record<string, string>, lookups: ImportLookupRecords): { record?: MasterRecord; error?: string } {
  const spec = relationSpec(field)!;
  if (field.name === "course_offering_id") return resolveOffering(row, lookups, spec.endpoint);
  if (field.name === "laboratory_batch_configuration_id") {
    const offering = resolveOffering(row, lookups, "/course-offerings");
    if (offering.error || !offering.record) return offering;
    return selectReference(lookups[spec.endpoint] ?? [], (record) => String(record.course_offering_id) === offering.record!.id, "laboratory batch configuration", spec.columns, row);
  }
  if (field.name === "academic_term_id") return resolveTerm(row.academic_term_code, lookups[spec.endpoint] ?? [], spec.columns, row);
  if (field.name === "section_id") {
    const term = resolveTerm(row.academic_term_code, lookups["/academic-terms"] ?? [], ["academic_term_code"], row);
    if (term.error || !term.record) return term;
    return selectReference(lookups[spec.endpoint] ?? [], (record) => normalize(record.section_code) === normalize(row.section_code) && String(record.academic_term_id) === term.record!.id, "section", spec.columns, row);
  }
  const definitions: Record<string, { recordKey: string; label: string; column: string }> = {
    department_id: { recordKey: "department_code", label: "department", column: "department_code" }, offering_department_id: { recordKey: "department_code", label: "department", column: "offering_department_code" }, owning_department_id: { recordKey: "department_code", label: "department", column: "department_code" },
    program_id: { recordKey: "program_code", label: "program", column: "program_code" }, faculty_id: { recordKey: "faculty_code", label: "faculty", column: "faculty_code" }, required_with_main_faculty_id: { recordKey: "faculty_code", label: "main faculty", column: "required_main_faculty_code" },
    course_id: { recordKey: "course_code", label: "course", column: "course_code" }, classroom_id: { recordKey: "room_number", label: "classroom", column: "classroom_number" }, preferred_classroom_id: { recordKey: "room_number", label: "preferred classroom", column: "classroom_number" }, primary_classroom_id: { recordKey: "room_number", label: "primary classroom", column: "primary_classroom_number" },
    laboratory_id: { recordKey: "laboratory_code", label: "laboratory", column: "laboratory_code" }, laboratory_override_id: { recordKey: "laboratory_code", label: "offering laboratory", column: "laboratory_code" }, preferred_laboratory_id: { recordKey: "laboratory_code", label: "preferred laboratory", column: "laboratory_code" }, default_laboratory_id: { recordKey: "laboratory_code", label: "preferred laboratory", column: "preferred_laboratory_code" }, working_day_id: { recordKey: "day_name", label: "working day", column: "day_name" },
    student_batch_id: { recordKey: "batch_name", label: "student group", column: "student_group_name" }, batch_id: { recordKey: "batch_name", label: "student group", column: "student_group_name" },
  };
  const definition = definitions[field.name];
  if (!definition) return { error: `No readable-key resolver is configured for ${field.name}.` };
  return selectReference(lookups[spec.endpoint] ?? [], (record) => normalize(record[definition.recordKey]) === normalize(row[definition.column]), definition.label, spec.columns, row);
}

function resolveOffering(row: Record<string, string>, lookups: ImportLookupRecords, endpoint: string) {
  const course = selectReference(lookups["/courses"] ?? [], (record) => normalize(record.course_code) === normalize(row.course_code), "course", ["course_code"], row);
  if (course.error || !course.record) return course;
  const term = resolveTerm(row.academic_term_code, lookups["/academic-terms"] ?? [], ["academic_term_code"], row);
  if (term.error || !term.record) return term;
  const section = selectReference(lookups["/sections"] ?? [], (record) => normalize(record.section_code) === normalize(row.section_code) && String(record.academic_term_id) === term.record!.id, "section", ["section_code", "academic_term_code"], row);
  if (section.error || !section.record) return section;
  return selectReference(lookups[endpoint] ?? [], (record) => String(record.course_id) === course.record!.id && String(record.section_id) === section.record!.id && String(record.academic_term_id) === term.record!.id, "course offering", ["course_code", "section_code", "academic_term_code"], row);
}

function resolveTerm(value: unknown, records: MasterRecord[], columns: string[], row: Record<string, string>) {
  return selectReference(records, (record) => termKey(record) === normalizeTerm(value), "academic term", columns, row);
}

function selectReference(records: MasterRecord[], predicate: (record: MasterRecord) => boolean, label: string, columns: string[], row: Record<string, string>): { record?: MasterRecord; error?: string } {
  const matches = records.filter(predicate);
  const active = matches.filter((record) => record.is_active !== false);
  const original = columns.map((column) => row[column]).filter(Boolean).join(" | ");
  if (active.length > 1) return { error: `Ambiguous ${label} reference '${original}': multiple active records match.` };
  if (active.length === 1) return { record: active[0] };
  if (matches.length) return { error: `Referenced ${label} '${original}' is inactive.` };
  return { error: `Unknown ${label} reference '${original}'.` };
}

function termKey(record: MasterRecord) { return `${normalize(record.academic_year)}|${normalize(record.term_name)}`; }
function normalizeTerm(value: unknown) {
  const raw = String(value ?? "").trim().toUpperCase();
  const match = raw.match(/^(\d{4}-\d{2})\s*(?:\||\/|:|\s)\s*([IV]+-[IV]+)$/);
  return match ? `${match[1]}|${match[2]}` : normalize(raw);
}
function normalize(value: unknown) { return String(value ?? "").trim().toUpperCase(); }
function comparable(value: unknown) { return typeof value === "boolean" ? String(value) : normalize(value); }
function parseOptionalBoolean(value: string | undefined): { value?: boolean; error?: string } {
  if (value == null || value.trim() === "") return {};
  const normalized = value.trim().toUpperCase();
  if (["TRUE", "1", "YES", "Y"].includes(normalized)) return { value: true };
  if (["FALSE", "0", "NO", "N"].includes(normalized)) return { value: false };
  return { error: `is_active must be TRUE or FALSE, received '${value}'.` };
}
