import type { MasterRecord } from "@/lib/master-data-api";
import type { SolverRun, TimetableVersion, ValidationRun } from "@/lib/types";
import { sectionLabel } from "@/lib/section-labels";

export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): boolean {
  return typeof value === "string" && uuidPattern.test(value);
}

export function readableRecordLabel(endpoint: string, row: MasterRecord): string {
  const values: Record<string, string[]> = {
    "/users": [text(row.username), text(row.full_name)],
    "/departments": [text(row.department_name), text(row.department_code)],
    "/programs": [text(row.program_name), text(row.program_code)],
    "/academic-terms": [text(row.academic_year), text(row.term_name)],
    "/sections": [text(row.display_label) || sectionLabel(row)],
    "/faculty": [text(row.faculty_code), text(row.full_name)],
    "/courses": [text(row.course_code), text(row.course_name)],
    "/classrooms": [text(row.display_label) || [text(row.room_number), text(row.room_name) || text(row.building_name), row.capacity == null ? "" : `Capacity ${row.capacity}`].filter(Boolean).join(" - ")],
    "/laboratories": [text(row.laboratory_name), text(row.laboratory_code)],
    "/working-days": [text(row.day_name)],
    "/student-batches": [text(row.batch_name)],
    "/course-offerings": [text(row.display_label)],
    "/laboratory-batch-configurations": [text(row.display_label)],
  };
  const parts = (values[endpoint] ?? [text(row.display_label), text(row.name), text(row.code)]).filter(Boolean);
  return parts.length ? parts.join(" - ") : "Metadata unavailable";
}

export function timetableVersionLabel(version: TimetableVersion): string {
  return `Version ${version.version_number}${version.version_name ? ` - ${version.version_name}` : ""}`;
}

export function validationRunLabel(run: ValidationRun, ordinal?: number): string {
  return `${ordinal ? `Run #${ordinal}` : "Validation run"} - ${run.status}`;
}

export function solverRunLabel(run: SolverRun, ordinal?: number): string {
  return `${ordinal ? `Run #${ordinal}` : "Solver run"} - ${run.status}`;
}

export function safeReadable(value: unknown, fallback = "Metadata unavailable"): string {
  if (value == null || value === "") return fallback;
  if (isUuid(value)) return fallback;
  return String(value);
}

export function stripIdentifierFields(row: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(row).filter(([key, value]) => !(key === "id" || key.endsWith("_id") || key.endsWith("_ids") || isUuid(value))));
}

function text(value: unknown) { return typeof value === "string" && !isUuid(value) ? value.trim() : ""; }
