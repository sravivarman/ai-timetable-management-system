import type { ImportLookupRecords, ImportReferenceResolution } from "@/lib/csv-import-resolution";
import type { MasterRecord } from "@/lib/master-data-api";
import { readableRecordLabel } from "@/lib/readable-labels";

export type ResolvedAvailabilitySlot = {
  academic_term_id: string;
  working_day_id: string;
  period_number: number;
  availability_type: "BLOCKED" | "ALLOWED";
};

const modeValues = new Set(["ALL_PERIODS", "EXCEPT_BLOCKED", "ONLY_SELECTED"]);
const dayAliases: Record<string, string> = {
  MON: "MONDAY", TUE: "TUESDAY", WED: "WEDNESDAY", THU: "THURSDAY",
  FRI: "FRIDAY", SAT: "SATURDAY",
};

export function resolveLaboratoryAvailabilityCsv(
  source: Record<string, string>,
  lookups: ImportLookupRecords,
): { slots: ResolvedAvailabilitySlot[]; references: ImportReferenceResolution[]; errors: string[] } {
  const mode = String(source.availability_mode ?? "ALL_PERIODS").trim().toUpperCase();
  const errors: string[] = [];
  const references: ImportReferenceResolution[] = [];
  if (!modeValues.has(mode)) errors.push(`Invalid availability_mode '${source.availability_mode}'. Use ALL_PERIODS, EXCEPT_BLOCKED, or ONLY_SELECTED.`);

  const hasSlots = Boolean(source.blocked_periods?.trim() || source.allowed_periods?.trim());
  const term = hasSlots ? resolveTerm(source.academic_term_code, lookups["/academic-terms"] ?? []) : {};
  if (term.error) errors.push(term.error);
  if (term.record) references.push({ targetField: "academic_term_id", sourceColumns: ["academic_term_code"], original: source.academic_term_code || "Current academic term", resolvedLabel: readableRecordLabel("/academic-terms", term.record) });

  const blocked = parseSlots(source.blocked_periods, "BLOCKED", term.record, lookups["/working-days"] ?? []);
  const allowed = parseSlots(source.allowed_periods, "ALLOWED", term.record, lookups["/working-days"] ?? []);
  errors.push(...blocked.errors, ...allowed.errors);
  references.push(...blocked.references, ...allowed.references);
  if (mode === "ALL_PERIODS" && (blocked.slots.length || allowed.slots.length)) errors.push("ALL_PERIODS must not define blocked_periods or allowed_periods.");
  if (mode === "EXCEPT_BLOCKED" && allowed.slots.length) errors.push("EXCEPT_BLOCKED accepts blocked_periods only.");
  if (mode === "ONLY_SELECTED" && blocked.slots.length) errors.push("ONLY_SELECTED accepts allowed_periods only.");
  if (mode === "ONLY_SELECTED" && !allowed.slots.length) errors.push("ONLY_SELECTED requires at least one allowed period.");
  return { slots: mode === "EXCEPT_BLOCKED" ? blocked.slots : mode === "ONLY_SELECTED" ? allowed.slots : [], references, errors };
}

export function compactAvailabilityPeriods(
  rows: MasterRecord[],
  days: MasterRecord[],
  availabilityType: "BLOCKED" | "ALLOWED",
): string {
  const dayById = new Map(days.map((day) => [day.id, shortDay(String(day.day_name))]));
  return rows
    .filter((row) => row.is_active !== false && String(row.availability_type ?? "BLOCKED") === availabilityType)
    .sort((a, b) => Number(days.find((day) => day.id === a.working_day_id)?.sequence_number ?? 99) - Number(days.find((day) => day.id === b.working_day_id)?.sequence_number ?? 99) || Number(a.period_number) - Number(b.period_number))
    .map((row) => `${dayById.get(String(row.working_day_id)) ?? "Day"}:P${row.period_number}`)
    .join("|");
}

function parseSlots(value: string | undefined, type: "BLOCKED" | "ALLOWED", term: MasterRecord | undefined, days: MasterRecord[]) {
  const slots: ResolvedAvailabilitySlot[] = []; const references: ImportReferenceResolution[] = []; const errors: string[] = [];
  const seen = new Set<string>();
  for (const token of String(value ?? "").split("|").map((item) => item.trim()).filter(Boolean)) {
    const match = token.match(/^([A-Za-z]+)\s*:\s*P?([1-7])$/i);
    if (!match) { errors.push(`Invalid availability slot '${token}'. Use Mon:P1|Wed:P6.`); continue; }
    const requestedDay = dayAliases[match[1].slice(0, 3).toUpperCase()] ?? match[1].toUpperCase();
    const matches = days.filter((day) => String(day.day_name).toUpperCase() === requestedDay);
    const active = matches.filter((day) => day.is_active !== false && day.is_working_day !== false);
    if (active.length > 1) { errors.push(`Ambiguous working day '${match[1]}'.`); continue; }
    if (!active.length) { errors.push(matches.length ? `Working day '${match[1]}' is inactive.` : `Unknown working day '${match[1]}'.`); continue; }
    if (!term) continue;
    const key = `${active[0].id}:${match[2]}`;
    if (seen.has(key)) { errors.push(`Duplicate availability slot '${token}'.`); continue; }
    seen.add(key);
    slots.push({ academic_term_id: term.id, working_day_id: active[0].id, period_number: Number(match[2]), availability_type: type });
    references.push({ targetField: `${type.toLowerCase()}_${key}`, sourceColumns: [type === "BLOCKED" ? "blocked_periods" : "allowed_periods"], original: token, resolvedLabel: `${active[0].day_name} · P${match[2]}` });
  }
  return { slots, references, errors };
}

function resolveTerm(value: string | undefined, terms: MasterRecord[]): { record?: MasterRecord; error?: string } {
  const active = terms.filter((term) => term.is_active !== false);
  if (value?.trim()) {
    const normalized = value.trim().toUpperCase().replace(/\s*(?:\||\/|:)\s*/, "|").replace(/\s+/, "|");
    const matches = active.filter((term) => `${term.academic_year}|${term.term_name}`.toUpperCase() === normalized);
    if (matches.length === 1) return { record: matches[0] };
    return { error: matches.length > 1 ? `Ambiguous academic term '${value}'.` : `Unknown or inactive academic term '${value}'.` };
  }
  const current = active.filter((term) => term.is_current === true);
  if (current.length === 1) return { record: current[0] };
  return { error: "academic_term_code is required when there is not exactly one current academic term." };
}

function shortDay(day: string) { return day.slice(0, 3); }
