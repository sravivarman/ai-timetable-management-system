import { describe, expect, it } from "vitest";
import { parseCsv } from "@/lib/csv-import";

describe("CSV import parser", () => {
  it("parses quoted values and escaped quotes", () => {
    const result = parseCsv('department_code,department_name,short_name\nCSE,"Computer Science, Engineering","C""SE"');
    expect(result.errors).toEqual([]);
    expect(result.rows[0]).toEqual({ department_code: "CSE", department_name: "Computer Science, Engineering", short_name: 'C"SE' });
  });

  it("reports rows with the wrong number of columns", () => {
    const result = parseCsv("code,name\nCSE");
    expect(result.errors[0]).toMatch(/Row 2/);
  });
});
