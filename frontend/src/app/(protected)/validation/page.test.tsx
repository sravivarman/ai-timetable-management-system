import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ValidationPage from "@/app/(protected)/validation/page";
import { listAcademicTerms, masterApi, validationApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({
  listAcademicTerms: vi.fn(),
  masterApi: { departments: vi.fn(), programs: vi.fn(), sections: vi.fn() },
  validationApi: { run: vi.fn(), list: vi.fn(), get: vi.fn(), issues: vi.fn() },
}));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: () => true }) }));

const termId = "00000000-0000-0000-0000-000000000001";
const run = { id: "00000000-0000-0000-0000-000000000010", academic_term_id: termId, scope_type: "COLLEGE", status: "WARNING", total_checks: 3, passed_checks: 2, failed_checks: 0, warning_checks: 1, started_at: "2026-08-03T12:00:00Z", completed_at: "2026-08-03T12:00:01Z", created_by: "user", created_at: "2026-08-03T12:00:00Z" };
const empty = { items: [], total: 0, page: 1, page_size: 10, pages: 0 };

describe("Validation page", () => {
  beforeEach(() => {
    vi.mocked(listAcademicTerms).mockResolvedValue({ ...empty, items: [{ id: termId, academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }] });
    vi.mocked(masterApi.departments).mockResolvedValue({ ...empty, items: [{ id: "00000000-0000-0000-0000-000000000002", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true }] });
    vi.mocked(masterApi.programs).mockResolvedValue(empty);
    vi.mocked(masterApi.sections).mockResolvedValue(empty);
    vi.mocked(validationApi.list).mockResolvedValue(empty);
    vi.mocked(validationApi.run).mockResolvedValue(run);
    vi.mocked(validationApi.get).mockResolvedValue(run);
    vi.mocked(validationApi.issues).mockResolvedValue(empty);
  });

  it("shows only the identifier selector required by the selected scope", async () => {
    renderWithProviders(<ValidationPage />);
    const user = userEvent.setup();
    expect(screen.queryByText("Department", { selector: "span" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Scope"), "DEPARTMENT");
    expect(await screen.findByText("Department", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByText("Program", { selector: "span" })).not.toBeInTheDocument();
  });

  it("submits an exact COLLEGE scope validation request", async () => {
    renderWithProviders(<ValidationPage />); const user = userEvent.setup();
    expect((await screen.findAllByRole("option", { name: "2026-27 · I-I" })).length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Academic term"), termId);
    await user.click(screen.getByRole("button", { name: "Run validation" }));
    await waitFor(() => expect(vi.mocked(validationApi.run).mock.calls[0]?.[0]).toEqual({ academic_term_id: termId, scope_type: "COLLEGE" }));
  });

  it("uses the shared term-aware label for Section scope", async () => {
    vi.mocked(masterApi.sections).mockResolvedValue({ ...empty, items: [{ id: "00000000-0000-0000-0000-000000000003", program_id: "00000000-0000-0000-0000-000000000004", academic_term_id: termId, section_code: "CSD-A", section_name: "A", student_strength: 72, is_active: true }] });
    renderWithProviders(<ValidationPage />); const user = userEvent.setup();
    expect((await screen.findAllByRole("option", { name: /2026-27.*I-I/ })).length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Academic term"), termId);
    await user.selectOptions(screen.getByLabelText("Scope"), "SECTION");
    expect(await screen.findByRole("option", { name: "2026-27 I-I • CSD-A" })).toBeInTheDocument();
    expect(screen.queryByText(/CSD-A.*·.*A/)).not.toBeInTheDocument();
  });

  it("renders paginated validation issue details", async () => {
    vi.mocked(validationApi.list).mockResolvedValue({ ...empty, items: [run], total: 1, pages: 1 });
    vi.mocked(validationApi.get).mockResolvedValue(run);
    vi.mocked(validationApi.issues).mockResolvedValue({ ...empty, total: 1, pages: 1, items: [{ id: "issue", severity: "WARNING", issue_code: "LAB_BATCH_COUNT_OVERRIDE", entity_type: "course_offering", entity_id: "offering", message: "Offering overrides course default", details: { effective_lab_group_count: 3 }, created_at: "2026-08-03T12:00:00Z" }] });
    renderWithProviders(<ValidationPage />); const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "View issues" }));
    expect(await screen.findByText("LAB_BATCH_COUNT_OVERRIDE")).toBeInTheDocument();
    expect(screen.getByText("Offering overrides course default")).toBeInTheDocument();
    expect(screen.getByText(/effective_lab_group_count/)).toBeInTheDocument();
  });
});
