import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdministrativeReportBuilder } from "@/components/administrative-report-builder";
import { listAcademicTerms, masterApi, reportsApi } from "@/lib/api";
import type { ReportDefinition } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", () => ({
  reportsApi: { definitions: vi.fn(), preview: vi.fn(), export: vi.fn() },
  listAcademicTerms: vi.fn(),
  masterApi: { departments: vi.fn(), programs: vi.fn(), sections: vi.fn(), courses: vi.fn(), faculty: vi.fn() },
}));

const columns = [
  { key: "faculty_code", label: "Faculty ID", group: "Faculty", data_type: "text", sortable: true, default_width: 15, alignment: "left" },
  { key: "faculty_name", label: "Faculty Name", group: "Faculty", data_type: "text", sortable: true, default_width: 28, alignment: "left" },
  { key: "department_name", label: "Department Name", group: "Academic", data_type: "text", sortable: true, default_width: 30, alignment: "left" },
  { key: "designation", label: "Designation", group: "Faculty", data_type: "text", sortable: true, default_width: 22, alignment: "left" },
];
const report = (key: string, title: string): ReportDefinition => ({ key, title, description: `${title} description`, layout_type: "TABULAR", columns, default_columns: ["faculty_code", "faculty_name"], filters: [{ key: "department_id", label: "Department", control: "entity", options: [] }], default_sort: [{ key: "department_name", direction: "asc" }], supported_formats: ["xlsx", "csv", "docx", "pdf"] });
const definitions = [report("faculty_master", "Faculty Master"), report("course_offerings", "Course Offerings"), report("theory_faculty_allocations", "Theory Faculty Allocations"), report("activity_faculty_allocations", "Activity Faculty Allocations"), report("section_course_faculty", "Section-wise Course & Faculty Allocation"), report("faculty_workload", "Faculty Workload")];
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 100, pages: items.length ? 1 : 0 });
const preview = { report_key: "faculty_master", title: "Faculty Master", columns: columns.slice(0, 2), filters: {}, filter_summary: ["Department: CSE • Computer Science and Engineering"], sorting: [{ key: "department_name", direction: "asc" as const }], rows: [{ faculty_code: "VCE042", faculty_name: "Dr. R. Kumar" }], total: 1, page: 1, page_size: 50, pages: 1, configuration_signature: "signature" };

describe("administrative report builder", () => {
  beforeEach(() => {
    replace.mockReset();
    vi.mocked(reportsApi.definitions).mockResolvedValue(definitions);
    vi.mocked(reportsApi.preview).mockResolvedValue(preview);
    vi.mocked(listAcademicTerms).mockResolvedValue(page([{ id: "term-1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }]));
    vi.mocked(masterApi.departments).mockResolvedValue(page([{ id: "dept-1", department_code: "CSE", department_name: "Computer Science and Engineering", short_name: "CSE", is_active: true }]));
    vi.mocked(masterApi.programs).mockResolvedValue(page([])); vi.mocked(masterApi.sections).mockResolvedValue(page([])); vi.mocked(masterApi.courses).mockResolvedValue(page([])); vi.mocked(masterApi.faculty).mockResolvedValue(page([]));
  });

  it("shows exactly the six administrative definitions and loads defaults", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="faculty_master" />);
    const selector = await screen.findByRole("combobox", { name: "Report" }); await user.click(selector);
    const list = screen.getByRole("listbox", { name: "Report options" });
    expect(within(list).getAllByRole("option")).toHaveLength(6);
    expect(screen.getByRole("checkbox", { name: "Faculty ID" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Faculty Name" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Designation" })).not.toBeChecked();
    for (const name of ["Excel", "CSV", "Word", "PDF"]) expect(screen.getByRole("button", { name: `Export ${name}` })).toBeInTheDocument();
  });

  it("supports select all, clear, restore defaults, and accessible reordering", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="faculty_master" />);
    await screen.findByRole("checkbox", { name: "Faculty ID" });
    await user.click(screen.getByRole("button", { name: "Select All" }));
    expect(screen.getAllByRole("checkbox").every((item) => (item as HTMLInputElement).checked)).toBe(true);
    await user.click(screen.getByRole("button", { name: "Clear All" }));
    expect(screen.getByRole("button", { name: "Preview Report" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Select at least one");
    await user.click(screen.getByRole("button", { name: /Restore Default/ }));
    await user.click(screen.getByRole("button", { name: "Move Faculty Name up" }));
    const order = screen.getByText("Selected Columns / Order").nextElementSibling!;
    expect(order.textContent?.indexOf("Faculty Name")).toBeLessThan(order.textContent?.indexOf("Faculty ID") ?? 0);
  });

  it("keeps filtering and sorting independent from displayed columns", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="faculty_master" />);
    await user.click(await screen.findByRole("combobox", { name: "Department" }));
    await user.click(screen.getByRole("option", { name: /CSE • Computer Science/ }));
    await user.click(screen.getByRole("button", { name: "Preview Report" }));
    await waitFor(() => expect(reportsApi.preview).toHaveBeenCalled());
    const payload = vi.mocked(reportsApi.preview).mock.calls.at(-1)![0];
    expect(payload.filters.department_id).toBe("dept-1");
    expect(payload.selected_columns).not.toContain("department_name");
    expect(payload.sort_fields).toEqual([{ key: "department_name", direction: "asc" }]);
  });

  it("renders preview in selected order with readable values and row count", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="faculty_master" />);
    await user.click(await screen.findByRole("button", { name: "Move Faculty Name up" }));
    vi.mocked(reportsApi.preview).mockResolvedValueOnce({ ...preview, columns: [columns[1], columns[0]], rows: [{ faculty_name: "Dr. R. Kumar", faculty_code: "VCE042" }] });
    await user.click(screen.getByRole("button", { name: "Preview Report" }));
    expect(await screen.findByText("Dr. R. Kumar")).toBeInTheDocument();
    const headers = screen.getAllByRole("columnheader").map((item) => item.textContent);
    expect(headers).toEqual(["Faculty Name", "Faculty ID"]);
    expect(screen.getByText("1 record")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i);
  });

  it("keeps MAIN and SUPPORTING activity allocations as distinct preview rows", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.preview).mockResolvedValueOnce({ ...preview, report_key: "activity_faculty_allocations", title: "Activity Faculty Allocations", columns: [{ ...columns[0], key: "faculty_role", label: "Faculty Role" }], rows: [{ faculty_role: "MAIN" }, { faculty_role: "SUPPORTING" }], total: 2 });
    renderWithProviders(<AdministrativeReportBuilder initialReportKey="activity_faculty_allocations" />);
    await user.click(await screen.findByRole("button", { name: "Preview Report" }));
    expect(await screen.findByText("MAIN")).toBeInTheDocument();
    expect(screen.getByText("SUPPORTING")).toBeInTheDocument();
    expect(screen.getByText("2 records")).toBeInTheDocument();
  });
});
