import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdministrativeReportBuilder } from "@/components/administrative-report-builder";
import { reportsApi } from "@/lib/api";
import type { ReportDefinition } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

const replace = vi.fn();
const authState = vi.hoisted(() => ({ reportViewer: false }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: (role: string) => authState.reportViewer && role === "REPORT_VIEWER" }) }));
vi.mock("@/lib/api", () => ({
  reportsApi: { definitions: vi.fn(), filterOptions: vi.fn(), preview: vi.fn(), export: vi.fn() },
}));

const columns = [
  { key: "faculty_code", label: "Faculty ID", group: "Faculty", data_type: "text", sortable: true, default_width: 15, alignment: "left" },
  { key: "faculty_name", label: "Faculty Name", group: "Faculty", data_type: "text", sortable: true, default_width: 28, alignment: "left" },
  { key: "department_name", label: "Department Name", group: "Academic", data_type: "text", sortable: true, default_width: 30, alignment: "left" },
  { key: "designation", label: "Designation", group: "Faculty", data_type: "text", sortable: true, default_width: 22, alignment: "left" },
];
const allEntityFilters = [
  { key: "academic_term_id", label: "Academic Term", control: "entity", options: [] },
  { key: "department_id", label: "Department", control: "entity", options: [] },
  { key: "program_id", label: "Program", control: "entity", options: [] },
  { key: "section_id", label: "Section", control: "entity", options: [] },
  { key: "course_id", label: "Course", control: "entity", options: [] },
  { key: "faculty_id", label: "Faculty", control: "entity", options: [] },
  { key: "faculty_department_id", label: "Faculty Department", control: "entity", options: [] },
];
const report = (key: string, title: string): ReportDefinition => ({ key, title, description: `${title} description`, layout_type: "TABULAR", columns, default_columns: ["faculty_code", "faculty_name"], filters: key === "theory_faculty_allocations" ? allEntityFilters : [{ key: "department_id", label: "Department", control: "entity", options: [] }], default_sort: [{ key: "department_name", direction: "asc" }], supported_formats: ["xlsx", "csv", "docx", "pdf"] });
const definitions = [report("faculty_master", "Faculty Master"), report("course_offerings", "Course Offerings"), report("theory_faculty_allocations", "Theory Faculty Allocations"), report("activity_faculty_allocations", "Activity Faculty Allocations"), report("section_course_faculty", "Section-wise Course & Faculty Allocation"), report("faculty_workload", "Faculty Workload")];
const preview = { report_key: "faculty_master", title: "Faculty Master", columns: columns.slice(0, 2), filters: {}, filter_summary: ["Department: CSE • Computer Science and Engineering"], sorting: [{ key: "department_name", direction: "asc" as const }], rows: [{ faculty_code: "VCE042", faculty_name: "Dr. R. Kumar" }], total: 1, page: 1, page_size: 50, pages: 1, configuration_signature: "signature" };

describe("administrative report builder", () => {
  beforeEach(() => {
    vi.clearAllMocks(); replace.mockReset();
    authState.reportViewer = false;
    vi.mocked(reportsApi.definitions).mockResolvedValue(definitions);
    vi.mocked(reportsApi.preview).mockResolvedValue(preview);
    vi.mocked(reportsApi.filterOptions).mockResolvedValue({ academic_terms: [{ id: "term-1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }], departments: [{ id: "dept-1", department_code: "CSE", department_name: "Computer Science and Engineering", short_name: "CSE", is_active: true }], programs: [{ id: "program-1", department_id: "dept-1", program_code: "BTECH-CSE", program_name: "B.Tech CSE", is_active: true }, { id: "program-2", department_id: "dept-2", program_code: "BTECH-ECE", program_name: "B.Tech ECE", is_active: true }], sections: [{ id: "section-1", program_id: "program-1", academic_term_id: "term-1", section_name: "A", section_code: "CSE-A", student_strength: 72, is_active: true }], courses: [{ id: "course-1", course_code: "CS301", course_name: "Operating Systems", offering_department_id: "dept-1", course_type: "THEORY", grouping_mode: "FULL_SECTION", venue_requirement: "CLASSROOM_ONLY", weekly_periods: 4, session_duration: 1, sessions_per_week: 4, default_group_count: 1, eligible_laboratory_ids: [], is_active: true }], faculty: [{ id: "faculty-1", faculty_code: "VCE042", full_name: "Dr. R. Kumar", department_id: "dept-1", designation: "Professor", institutional_email: "r.kumar@vce.ac.in", minimum_weekly_workload: 8, maximum_weekly_workload: 16, is_active: true }] });
    vi.mocked(reportsApi.export).mockResolvedValue({ blob: new Blob(["report"]), filename: "report.csv" });
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
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

  it("keeps all report downloads visible but hides operational tools for Report Viewer", async () => {
    authState.reportViewer = true;
    renderWithProviders(<AdministrativeReportBuilder initialReportKey="faculty_master" />);
    await screen.findByRole("button", { name: "Export Excel" });
    expect(screen.queryByRole("link", { name: "Operational reports" })).not.toBeInTheDocument();
    for (const name of ["Excel", "CSV", "Word", "PDF"]) expect(screen.getByRole("button", { name: `Export ${name}` })).toBeEnabled();
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

  it("normalizes every entity selector All value before lookup and preview requests", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="theory_faculty_allocations" />);
    await screen.findByRole("combobox", { name: "Program" });
    await waitFor(() => expect(reportsApi.filterOptions).toHaveBeenCalled());
    for (const label of ["Academic Term", "Department", "Program", "Section", "Course", "Faculty", "Faculty Department"]) {
      const selector = screen.getByRole("combobox", { name: label });
      await user.click(selector);
      await user.click(screen.getByRole("option", { name: "All" }));
    }
    await user.click(screen.getByRole("button", { name: "Preview Report" }));
    await waitFor(() => expect(reportsApi.preview).toHaveBeenCalled());
    expect(vi.mocked(reportsApi.preview).mock.calls.at(-1)![0].filters).toEqual({});
    expect(reportsApi.filterOptions).toHaveBeenCalledTimes(1);
  });

  it("uses the same normalized All configuration for every export format", async () => {
    const user = userEvent.setup(); renderWithProviders(<AdministrativeReportBuilder initialReportKey="theory_faculty_allocations" />);
    await screen.findByRole("button", { name: "Export Excel" });
    await user.click(screen.getByRole("combobox", { name: "Academic Term" }));
    await user.click(screen.getByRole("option", { name: "All" }));
    for (const name of ["Excel", "CSV", "Word", "PDF"]) {
      await user.click(screen.getByRole("button", { name: `Export ${name}` }));
      await waitFor(() => expect(reportsApi.export).toHaveBeenCalledTimes(name === "Excel" ? 1 : name === "CSV" ? 2 : name === "Word" ? 3 : 4));
    }
    for (const [payload] of vi.mocked(reportsApi.export).mock.calls) expect(payload.filters).toEqual({});
  });

  it("preserves valid narrower children for parent All but clears incompatible children", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.filterOptions).mockResolvedValue({ ...(await reportsApi.filterOptions()), departments: [{ id: "dept-1", department_code: "CSE", department_name: "Computer Science and Engineering", short_name: "CSE", is_active: true }, { id: "dept-2", department_code: "ECE", department_name: "Electronics and Communication Engineering", short_name: "ECE", is_active: true }] });
    renderWithProviders(<AdministrativeReportBuilder initialReportKey="theory_faculty_allocations" />);
    await user.click(await screen.findByRole("combobox", { name: "Program" })); await user.click(screen.getByRole("option", { name: /BTECH-CSE/ }));
    await user.click(screen.getByRole("combobox", { name: "Department" })); await user.click(screen.getByRole("option", { name: "All" }));
    expect((screen.getByRole("combobox", { name: "Program" }) as HTMLInputElement).value).toContain("BTECH-CSE");
    await user.click(document.body);
    await user.click(screen.getByRole("combobox", { name: "Department" })); await user.click(screen.getByRole("option", { name: /ECE •/ }));
    expect(screen.getByRole("combobox", { name: "Program" })).toHaveValue("All");
  });
});
