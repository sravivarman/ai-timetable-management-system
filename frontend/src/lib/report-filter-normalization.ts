/** Canonical optional-filter normalization shared by report lookups, preview, and export. */

export const REPORT_ENTITY_FILTER_KEYS = new Set([
  "academic_term_id",
  "department_id",
  "program_id",
  "section_id",
  "course_id",
  "faculty_id",
  "faculty_department_id",
]);

export function normalizeOptionalEntityFilter(value: string | null | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized && normalized.toUpperCase() !== "ALL" ? normalized : undefined;
}

export function normalizeReportFilters(filters: Record<string, string | null | undefined>): Record<string, string> {
  const normalized: Record<string, string> = {};
  for (const [key, raw] of Object.entries(filters)) {
    const value = REPORT_ENTITY_FILTER_KEYS.has(key) ? normalizeOptionalEntityFilter(raw) : raw?.trim() || undefined;
    if (value !== undefined) normalized[key] = value;
  }
  return normalized;
}

export function normalizeEntityLookupParams<T extends Record<string, string | null | undefined>>(params: T): Partial<Record<keyof T, string>> {
  return Object.fromEntries(Object.entries(params).flatMap(([key, value]) => {
    const normalized = normalizeOptionalEntityFilter(value);
    return normalized ? [[key, normalized]] : [];
  })) as Partial<Record<keyof T, string>>;
}
