import type { ResourceDateException } from "@/lib/types";

export const RESOURCE_DATE_EXCEPTION_HEADERS = [
  "resource_type", "resource_code", "academic_term_code", "exception_date",
  "period_start", "period_end", "availability_status", "reason",
] as const;

export type DateExceptionStatus = "NEW" | "IDENTICAL" | "CHANGED" | "INVALID" | "CONFLICT";
export type ResolvedDateException = {
  rowNumber: number;
  source: Record<string, string>;
  status: DateExceptionStatus;
  message: string;
  existing?: ResourceDateException;
  payload?: {
    resource_type: string; resource_id: string; academic_term_id: string;
    exception_date: string; period_start: number | null; period_end: number | null;
    availability_status: "AVAILABLE" | "UNAVAILABLE"; reason: string | null;
  };
};

type RecordLike = Record<string, unknown>;

export function resourceDateExceptionTemplate(resourceType = "LABORATORY") {
  return [{
    resource_type: resourceType,
    resource_code: "LAB3201",
    academic_term_code: "2026-27 | I-I",
    exception_date: "2026-09-18",
    period_start: "1",
    period_end: "3",
    availability_status: "UNAVAILABLE",
    reason: "Maintenance",
  }];
}

export function resourceDateExceptionExportRows(
  resourceType: string,
  resource: RecordLike,
  term: RecordLike,
  rows: ResourceDateException[],
) {
  const code = businessCode(resourceType, resource);
  const termCode = `${String(term.academic_year ?? "")} | ${String(term.term_name ?? "")}`;
  return rows.map((row) => ({
    resource_type: resourceType,
    resource_code: code,
    academic_term_code: termCode,
    exception_date: row.exception_date,
    period_start: row.period_start ?? "",
    period_end: row.period_end ?? "",
    availability_status: row.availability_status,
    reason: row.reason ?? "",
  }));
}

export function resolveResourceDateExceptionRows(
  sources: Record<string, string>[],
  resourceType: string,
  resource: RecordLike,
  term: RecordLike,
  existing: ResourceDateException[],
): ResolvedDateException[] {
  const expectedType = resourceType.toUpperCase();
  const expectedCode = businessCode(expectedType, resource).toUpperCase();
  const acceptedTerms = new Set([
    `${String(term.academic_year ?? "")} | ${String(term.term_name ?? "")}`.toUpperCase(),
    `${String(term.academic_year ?? "")} ${String(term.term_name ?? "")}`.toUpperCase(),
    String(term.term_name ?? "").toUpperCase(),
  ]);
  const keyCounts = new Map<string, number>();
  for (const source of sources) {
    const key = sourceKey(source);
    keyCounts.set(key, (keyCounts.get(key) ?? 0) + 1);
  }
  return sources.map((source, index) => {
    const errors: string[] = [];
    const type = source.resource_type.trim().toUpperCase();
    const code = source.resource_code.trim().toUpperCase();
    const termCode = source.academic_term_code.trim().toUpperCase();
    if (type !== expectedType) errors.push(`Expected resource_type ${expectedType}.`);
    if (code !== expectedCode) errors.push(`Unknown or unrelated resource code ${source.resource_code || "(blank)"}.`);
    if (!acceptedTerms.has(termCode)) errors.push(`Unknown or unrelated Academic Term ${source.academic_term_code || "(blank)"}.`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(source.exception_date.trim())) errors.push("exception_date must use YYYY-MM-DD.");
    const blankStart = source.period_start.trim() === "";
    const blankEnd = source.period_end.trim() === "";
    const start = blankStart ? null : Number(source.period_start);
    const end = blankEnd ? null : Number(source.period_end);
    if (blankStart !== blankEnd || (start !== null && (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end! > 7 || end! < start))) errors.push("Periods must both be blank for all day, or a valid inclusive range from 1 to 7.");
    const availability = source.availability_status.trim().toUpperCase();
    if (availability !== "AVAILABLE" && availability !== "UNAVAILABLE") errors.push("availability_status must be AVAILABLE or UNAVAILABLE.");
    const duplicate = (keyCounts.get(sourceKey(source)) ?? 0) > 1;
    if (duplicate) errors.push("Duplicate business key in this CSV file.");
    if (errors.length) return { rowNumber: index + 2, source, status: duplicate ? "CONFLICT" : "INVALID", message: errors.join(" ") };
    const payload = {
      resource_type: expectedType,
      resource_id: String(resource.id),
      academic_term_id: String(term.id),
      exception_date: source.exception_date.trim(),
      period_start: start,
      period_end: end,
      availability_status: availability as "AVAILABLE" | "UNAVAILABLE",
      reason: source.reason.trim() || null,
    };
    const current = existing.find((row) => row.exception_date === payload.exception_date && row.period_start === payload.period_start && row.period_end === payload.period_end && row.is_active !== false);
    if (!current) return { rowNumber: index + 2, source, status: "NEW", message: "Ready to create.", payload };
    const identical = current.availability_status === payload.availability_status && (current.reason ?? null) === payload.reason;
    return { rowNumber: index + 2, source, status: identical ? "IDENTICAL" : "CHANGED", message: identical ? "An identical exception already exists." : "Review and approve replacement of the existing exception.", existing: current, payload };
  });
}

function sourceKey(row: Record<string, string>) {
  return [row.resource_type, row.resource_code, row.academic_term_code, row.exception_date, row.period_start, row.period_end].map((value) => value.trim().toUpperCase()).join("|");
}

function businessCode(resourceType: string, resource: RecordLike) {
  if (resourceType === "FACULTY" || resourceType === "VISITING_FACULTY") return String(resource.faculty_code ?? "");
  if (resourceType === "LABORATORY") return String(resource.laboratory_code ?? "");
  return String(resource.room_number ?? resource.resource_code ?? "");
}
