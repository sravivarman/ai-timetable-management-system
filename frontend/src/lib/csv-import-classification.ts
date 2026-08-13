import type { MasterConfig, MasterField } from "@/lib/master-data-config";
import type { MasterRecord } from "@/lib/master-data-api";
import { readableRecordLabel } from "@/lib/readable-labels";
import {
  findExistingImportRecord,
  importBusinessKey,
  relationSpec,
  type ImportLookupRecords,
  type ResolvedImportRow,
} from "@/lib/csv-import-resolution";

export type ImportClassification = "NEW" | "IDENTICAL" | "CHANGED" | "INVALID" | "CONFLICT";
export type ImportResolution = "CREATED" | "UPDATED" | "KEPT_EXISTING" | "NO_CHANGES";
export type ImportRowStatus = ImportClassification | ImportResolution;

export type ImportFieldDiff = {
  field: string;
  label: string;
  existing: unknown;
  imported: unknown;
  existingLabel: string;
  importedLabel: string;
};

export type ClassifiedImportRow = ResolvedImportRow & {
  rowNumber: number;
  businessKey?: string;
  identityLabel: string;
  status: ImportRowStatus;
  existing?: MasterRecord;
  baseline?: MasterRecord;
  differences: ImportFieldDiff[];
  messages: string[];
};

export function classifyImportRows(config: MasterConfig, rows: ResolvedImportRow[], lookups: ImportLookupRecords): ClassifiedImportRow[] {
  const current = lookups[config.endpoint] ?? [];
  const classified = rows.map((row, index): ClassifiedImportRow => {
    const businessKey = importBusinessKey(config, row.payload);
    const match = findExistingImportRecord(config, row.payload, current);
    const messages = [...row.errors];
    if (match.error) messages.push(match.error);
    const status: ImportClassification = messages.length ? (match.error?.includes("ambiguous") ? "CONFLICT" : "INVALID") : match.record ? "IDENTICAL" : "NEW";
    const differences = match.record ? meaningfulDifferences(config, match.record, row.payload, row.source, lookups) : [];
    return {
      ...row,
      rowNumber: index + 2,
      businessKey,
      identityLabel: importIdentityLabel(config, row, match.record),
      status: status === "IDENTICAL" && differences.length ? "CHANGED" : status,
      existing: match.record,
      baseline: match.record ? { ...match.record } : undefined,
      differences,
      messages,
    };
  });

  const groups = new Map<string, ClassifiedImportRow[]>();
  for (const row of classified) if (row.businessKey && !row.errors.length) groups.set(row.businessKey, [...(groups.get(row.businessKey) ?? []), row]);
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    const first = group[0];
    const contradictory = group.some((row) => !payloadsEquivalent(config, first.payload, row.payload));
    if (contradictory) {
      for (const row of group) {
        row.status = "CONFLICT";
        row.messages.push("Contradictory rows use the same business key in this CSV. Choose one definition and upload again.");
      }
    } else {
      for (const row of group.slice(1)) {
        row.status = "IDENTICAL";
        row.messages.push(`Duplicate of CSV row ${first.rowNumber}; one write will be performed at most.`);
      }
    }
  }
  return classified;
}

export function meaningfulDifferences(config: MasterConfig, existing: MasterRecord, payload: Record<string, unknown>, source: Record<string, string>, lookups: ImportLookupRecords): ImportFieldDiff[] {
  const fields = comparisonFields(config, source);
  const differences = fields.flatMap((field) => {
    const imported = payload[field.name];
    const current = existing[field.name];
    if (equivalent(field.name, current, imported)) return [];
    return [{
      field: field.name,
      label: field.label,
      existing: current,
      imported,
      existingLabel: displayValue(field, current, lookups),
      importedLabel: displayValue(field, imported, lookups),
    }];
  });
  if (source.is_active?.trim() && !equivalent("is_active", existing.is_active, payload.is_active)) differences.push({ field: "is_active", label: "Active status", existing: existing.is_active, imported: payload.is_active, existingLabel: existing.is_active === false ? "Inactive" : "Active", importedLabel: payload.is_active === false ? "Inactive" : "Active" });
  return differences;
}

export function baselineStillMatches(config: MasterConfig, baseline: MasterRecord, current: MasterRecord, source: Record<string, string>): boolean {
  return comparisonFields(config, source).every((field) => equivalent(field.name, baseline[field.name], current[field.name]))
    && equivalent("is_active", baseline.is_active, current.is_active)
    && (!baseline.updated_at || !current.updated_at || String(baseline.updated_at) === String(current.updated_at));
}

export function importSummary(rows: ClassifiedImportRow[]) {
  const count = (status: ImportRowStatus) => rows.filter((row) => row.status === status).length;
  return {
    total: rows.length,
    new: count("NEW"),
    changed: count("CHANGED"),
    identical: count("IDENTICAL"),
    invalid: count("INVALID"),
    conflicts: count("CONFLICT"),
    created: count("CREATED"),
    updated: count("UPDATED"),
    keptExisting: count("KEPT_EXISTING"),
    noChanges: count("NO_CHANGES") + count("IDENTICAL"),
  };
}

export function updatePayload(row: ClassifiedImportRow): Record<string, unknown> {
  return Object.fromEntries(Object.entries(row.payload).filter(([key]) => key !== "is_active"));
}

function comparisonFields(config: MasterConfig, source: Record<string, string>): MasterField[] {
  return config.fields.filter((field) => {
    if (field.name === "user_id") return false;
    if (field.name === "is_active") return source.is_active?.trim() !== "";
    const columns = relationSpec(field)?.columns ?? [field.name];
    return columns.some((column) => Object.hasOwn(source, column));
  });
}

function payloadsEquivalent(config: MasterConfig, left: Record<string, unknown>, right: Record<string, unknown>): boolean {
  return [...config.fields.map((field) => field.name), "is_active"].every((field) => equivalent(field, left[field], right[field]));
}

function equivalent(field: string, left: unknown, right: unknown): boolean {
  if (Array.isArray(left) || Array.isArray(right)) return normalizedArray(left).join("|") === normalizedArray(right).join("|");
  if (left == null || left === "") return right == null || right === "";
  if (right == null || right === "") return false;
  if (typeof left === "boolean" || typeof right === "boolean") return normalizeBoolean(left) === normalizeBoolean(right);
  if (typeof left === "number" || typeof right === "number") return Number(left) === Number(right);
  const a = collapse(left); const b = collapse(right);
  if (field.includes("email")) return a.toLowerCase() === b.toLowerCase();
  if (field.includes("name")) return a.toLocaleLowerCase() === b.toLocaleLowerCase();
  return a.toUpperCase() === b.toUpperCase();
}

function normalizedArray(value: unknown): string[] {
  const values = Array.isArray(value) ? value : value == null || value === "" ? [] : String(value).split(/[|;]/);
  return values.map((item) => collapse(item).toUpperCase()).filter(Boolean).sort();
}

function collapse(value: unknown) { return String(value ?? "").trim().replace(/\s+/g, " "); }
function normalizeBoolean(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1;
  return ["1", "true", "yes", "y"].includes(String(value).trim().toLowerCase());
}

function displayValue(field: MasterField, value: unknown, lookups: ImportLookupRecords): string {
  if (value == null || value === "") return "Not set";
  if (field.lookup) {
    const ids = Array.isArray(value) ? value.map(String) : [String(value)];
    const records = lookups[field.lookup.endpoint] ?? [];
    return ids.map((id) => {
      const record = records.find((item) => item.id === id);
      return record ? readableRecordLabel(field.lookup!.endpoint, record) : "Referenced record unavailable";
    }).sort().join("; ");
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return Array.isArray(value) ? value.map(String).sort().join("; ") : String(value);
}

function importIdentityLabel(config: MasterConfig, row: ResolvedImportRow, existing: MasterRecord | undefined): string {
  const source = row.source;
  if (config.slug === "theory-allocations" || config.slug === "laboratory-allocations" || config.slug === "course-offerings") return [source.course_code, source.section_code, source.academic_term_code].filter(Boolean).join(" • ");
  if (existing) return readableRecordLabel(config.endpoint, existing);
  const candidates = [source.faculty_code, source.course_code, source.department_code, source.program_code, source.section_code, source.laboratory_code, source.classroom_number, source.room_number, source.academic_term_code, source.day_name, source.student_group_name];
  const primary = candidates.find(Boolean);
  const name = source.full_name || source.course_name || source.department_name || source.program_name || source.laboratory_name || source.room_name;
  if (primary) return [primary, name].filter(Boolean).join(" • ");
  const resolved = row.references.find((reference) => reference.resolvedLabel)?.resolvedLabel;
  return resolved ?? `${config.singular} CSV row`;
}
