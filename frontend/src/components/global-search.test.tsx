import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GlobalSearch } from "@/components/global-search";
import { listAcademicTerms, masterApi, timetableApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({ listAcademicTerms: vi.fn(), timetableApi: { list: vi.fn() }, masterApi: { departments: vi.fn(), programs: vi.fn(), sections: vi.fn(), faculty: vi.fn(), classrooms: vi.fn(), laboratories: vi.fn(), courses: vi.fn() } }));
const page = { items: [], total: 0, page: 1, page_size: 100, pages: 0 };
describe("global search", () => {
  it("finds timetables and provides a quick jump", async () => { vi.mocked(timetableApi.list).mockResolvedValue({ ...page, items: [{ id: "tt-1", academic_term_id: "term", scope_type: "COLLEGE", name: "CSE Master Timetable", status: "DRAFT", active_version_id: "version-1", created_by: "user", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] }); vi.mocked(listAcademicTerms).mockResolvedValue(page as never); for (const method of [masterApi.departments, masterApi.programs, masterApi.sections, masterApi.faculty, masterApi.classrooms, masterApi.laboratories, masterApi.courses]) vi.mocked(method).mockResolvedValue(page as never); const user = userEvent.setup(); renderWithProviders(<GlobalSearch />); await user.click(screen.getByRole("button", { name: /Search/i })); await user.type(screen.getByRole("textbox", { name: /Search timetables/i }), "CSE"); expect(await screen.findByRole("option", { name: /CSE Master Timetable Timetable/i })).toHaveAttribute("href", "/timetables/tt-1"); expect(screen.getByText("CSE Master Timetable · active version")).toBeInTheDocument(); });
  it("searches readable program, department, and academic-term labels", async () => { vi.mocked(timetableApi.list).mockResolvedValue(page as never); vi.mocked(listAcademicTerms).mockResolvedValue({ ...page, items: [{ id: "t1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }] }); vi.mocked(masterApi.departments).mockResolvedValue({ ...page, items: [{ id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true }] }); vi.mocked(masterApi.programs).mockResolvedValue({ ...page, items: [{ id: "p1", department_id: "d1", program_code: "CSE-UG", program_name: "B.Tech Computer Science", is_active: true }] }); for (const method of [masterApi.sections, masterApi.faculty, masterApi.classrooms, masterApi.laboratories, masterApi.courses]) vi.mocked(method).mockResolvedValue(page as never); const user = userEvent.setup(); renderWithProviders(<GlobalSearch />); await user.click(screen.getByRole("button", { name: /Search/i })); await user.type(screen.getByRole("textbox", { name: /Search timetables/i }), "2026"); expect(await screen.findByRole("option", { name: /2026-27.*Academic Term/i })).toHaveAttribute("href", expect.stringContaining("/master-data/academic-terms")); });
  it("shows a term-aware section result without duplicating its letter", async () => {
    vi.mocked(timetableApi.list).mockResolvedValue(page as never);
    vi.mocked(listAcademicTerms).mockResolvedValue({ ...page, items: [{ id: "term-1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }] });
    vi.mocked(masterApi.sections).mockResolvedValue({ ...page, items: [{ id: "section-1", program_id: "program-1", academic_term_id: "term-1", section_code: "CSD-A", section_name: "A", student_strength: 72, is_active: true }] });
    for (const method of [masterApi.departments, masterApi.programs, masterApi.faculty, masterApi.classrooms, masterApi.laboratories, masterApi.courses]) vi.mocked(method).mockResolvedValue(page as never);
    const user = userEvent.setup(); renderWithProviders(<GlobalSearch />);
    await user.click(screen.getByRole("button", { name: /Search/i }));
    await user.type(screen.getByRole("textbox", { name: /Search timetables/i }), "CSD-A");
    expect(await screen.findByRole("option", { name: /2026-27 I-I.*CSD-A.*Section/i })).toBeInTheDocument();
    expect(screen.queryByText(/CSD-A.*·.*A/)).not.toBeInTheDocument();
  });
});
