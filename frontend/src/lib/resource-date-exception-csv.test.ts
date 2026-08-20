import { describe, expect, it } from "vitest";
import { RESOURCE_DATE_EXCEPTION_HEADERS, resolveResourceDateExceptionRows, resourceDateExceptionExportRows } from "@/lib/resource-date-exception-csv";

const resource = { id: "lab-id", laboratory_code: "LAB3201" };
const term = { id: "term-id", academic_year: "2026-27", term_name: "I-I" };
const source = { resource_type: "LABORATORY", resource_code: "LAB3201", academic_term_code: "2026-27 | I-I", exception_date: "2026-09-18", period_start: "1", period_end: "3", availability_status: "UNAVAILABLE", reason: "Maintenance" };

describe("resource date exception business-key CSV", () => {
  it("resolves readable keys to hidden UUID payloads", () => {
    const row = resolveResourceDateExceptionRows([source], "LABORATORY", resource, term, [])[0];
    expect(row.status).toBe("NEW");
    expect(row.payload).toMatchObject({ resource_id: "lab-id", academic_term_id: "term-id", period_start: 1, period_end: 3 });
  });

  it("classifies identical, changed, and duplicate rows safely", () => {
    const existing = [{ id: "exception-id", resource_type: "LABORATORY", resource_id: "lab-id", academic_term_id: "term-id", exception_date: "2026-09-18", period_start: 1, period_end: 3, availability_status: "UNAVAILABLE" as const, reason: "Maintenance", is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }];
    expect(resolveResourceDateExceptionRows([source], "LABORATORY", resource, term, existing)[0].status).toBe("IDENTICAL");
    expect(resolveResourceDateExceptionRows([{ ...source, reason: "Exam" }], "LABORATORY", resource, term, existing)[0].status).toBe("CHANGED");
    expect(resolveResourceDateExceptionRows([source, source], "LABORATORY", resource, term, [])[0].status).toBe("CONFLICT");
  });

  it("exports only readable business keys", () => {
    const rows = resourceDateExceptionExportRows("LABORATORY", resource, term, [{ id: "exception-id", resource_type: "LABORATORY", resource_id: "lab-id", academic_term_id: "term-id", exception_date: "2026-09-18", period_start: null, period_end: null, availability_status: "UNAVAILABLE", reason: null, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]);
    expect(Object.keys(rows[0])).toEqual([...RESOURCE_DATE_EXCEPTION_HEADERS]);
    expect(Object.keys(rows[0]).some((key) => key.endsWith("_id"))).toBe(false);
  });
});
