import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportsPage from "@/app/(protected)/reports/page";
import { listAcademicTerms, masterApi, solverApi, timetableApi, validationApi, versionOperationsApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

let currentParams = ""; const replace = vi.fn();
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(currentParams), useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", () => ({
  listAcademicTerms: vi.fn(),
  timetableApi: { list: vi.fn(), versions: vi.fn(), viewGrid: vi.fn(), conflicts: vi.fn() },
  masterApi: { programs: vi.fn(), sections: vi.fn(), faculty: vi.fn(), classrooms: vi.fn(), laboratories: vi.fn(), studentBatches: vi.fn(), workingDays: vi.fn(), workload: vi.fn() },
  solverApi: { list: vi.fn() }, validationApi: { list: vi.fn() }, versionOperationsApi: { free: vi.fn() },
}));
vi.mock("@/components/resource-availability-manager", () => ({ ResourceAvailabilityManager: () => <div>Resource availability</div> }));

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 100, pages: items.length ? 1 : 0 });
const term = { id: "term-1", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true };
const timetable = { id: "tt-1", academic_term_id: "term-1", scope_type: "SECTION", section_id: "section-1", name: "CSE Published Timetable", status: "PUBLISHED", active_version_id: "version-active", created_by: "user", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const secondTimetable = { ...timetable, id: "tt-2", name: "CSE Review Timetable", status: "UNDER_REVIEW", active_version_id: "version-2" };
const activeVersion = { id: "version-active", timetable_id: "tt-1", version_number: 2, version_name: "Final", source_type: "SOLVER", validation_run_id: "validation", solver_status: "OPTIMAL", is_active: true, is_locked: false, created_by: "user", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const section = { id: "section-1", program_id: "program-1", academic_term_id: "term-1", section_name: "A", section_code: "CSE-A", student_strength: 72, is_active: true };
const grid = { version_id: "version-active", view_type: "section", resource_id: "section-1", schedule_type: "HIGHER_YEAR", days: [{ working_day_id: "day-1", day_name: "Monday", sequence_number: 1, entries: [{ entry_id: "entry-1", working_day_id: "day-1", day_name: "Monday", period_number: 1, period_numbers: [1], schedule_type: "HIGHER_YEAR", start_time: "09:10", end_time: "10:10", course_code: "CS101", course_name: "Programming", course_type: "THEORY", section_code: "CSE-A", session_length: 1, entry_status: "GENERATED", is_manual: false, is_locked: false }] }] };

describe("readable dependent report selectors", () => {
  beforeEach(() => {
    currentParams = ""; replace.mockReset(); vi.mocked(listAcademicTerms).mockResolvedValue(page([term])); vi.mocked(timetableApi.list).mockResolvedValue(page([timetable, secondTimetable])); vi.mocked(timetableApi.versions).mockResolvedValue(page([activeVersion])); vi.mocked(timetableApi.viewGrid).mockResolvedValue(grid); vi.mocked(masterApi.programs).mockResolvedValue(page([{ id: "program-1", department_id: "department-1", program_code: "CSE-UG", program_name: "B.Tech CSE", is_active: true }])); vi.mocked(masterApi.sections).mockResolvedValue(page([section])); vi.mocked(masterApi.faculty).mockResolvedValue(page([{ id: "faculty-1", faculty_code: "VCE001", full_name: "Faculty One", department_id: "department-1", designation: "Professor", institutional_email: "one@vce.ac.in", minimum_weekly_workload: 8, maximum_weekly_workload: 16, is_active: true }])); vi.mocked(masterApi.classrooms).mockResolvedValue(page([{ id: "room-1", room_number: "3204", room_name: "CSE Classroom", is_active: true }])); vi.mocked(masterApi.laboratories).mockResolvedValue(page([{ id: "lab-1", laboratory_code: "CSE-LAB", laboratory_name: "Programming Lab", room_number: "3102", is_active: true }])); vi.mocked(masterApi.studentBatches).mockResolvedValue(page([{ id: "batch-1", section_id: "section-1", batch_name: "A1", sequence_number: 1, student_count: 36, is_active: true }])); vi.mocked(masterApi.workingDays).mockResolvedValue(page([{ id: "day-1", day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true }])); vi.mocked(masterApi.workload).mockResolvedValue([]); vi.mocked(solverApi.list).mockResolvedValue(page([])); vi.mocked(validationApi.list).mockResolvedValue(page([])); vi.mocked(versionOperationsApi.free).mockResolvedValue({ version_id: "version-active", working_day_id: "day-1", period_number: 1, items: [] }); vi.mocked(timetableApi.conflicts).mockResolvedValue({ version_id: "version-active", conflicts: [], summary: { total: 0 } });
  });

  it("defaults to the active academic term", async () => { renderWithProviders(<ReportsPage />); await waitFor(() => expect(replace).toHaveBeenCalledWith(expect.stringContaining("academic_term_id=term-1"), { scroll: false })); });

  it("defaults to the published timetable and its active version", async () => { currentParams = "report=section-timetable&academic_term_id=term-1"; renderWithProviders(<ReportsPage />); await waitFor(() => expect(replace).toHaveBeenCalledWith(expect.stringMatching(/timetable_id=tt-1.*version_id=version-active/), { scroll: false })); });

  it("persists a timetable change together with its active version", async () => { currentParams = "report=section-timetable&academic_term_id=term-1"; const user = userEvent.setup(); renderWithProviders(<ReportsPage />); const selector = await screen.findByRole("combobox", { name: "Timetable" }); await user.click(selector); await user.click(screen.getByRole("option", { name: /CSE Review Timetable/i })); expect(replace).toHaveBeenCalledWith(expect.stringContaining("timetable_id=tt-2"), { scroll: false }); expect(replace).toHaveBeenCalledWith(expect.stringContaining("version_id=version-2"), { scroll: false }); });

  it("shows term-aware section labels without repeating the section letter while retaining IDs in the URL", async () => { currentParams = "report=section-timetable&academic_term_id=term-1&timetable_id=tt-1&version_id=version-active&resource_id=section-1"; renderWithProviders(<ReportsPage />); expect(await screen.findByDisplayValue("CSE Published Timetable")).toBeInTheDocument(); expect(screen.getByDisplayValue("Version 2 · Final")).toBeInTheDocument(); expect(await screen.findByDisplayValue("2026-27 I-I • CSE-A")).toBeInTheDocument(); expect(screen.queryByText(/CSE-A.*Section A/)).not.toBeInTheDocument(); });

  it("shows a loading state while scoped resource options load", async () => { currentParams = "report=section-timetable&academic_term_id=term-1&timetable_id=tt-1&version_id=version-active"; let resolve!: (value: { items: typeof section[]; total: number; page: number; page_size: number; pages: number }) => void; vi.mocked(masterApi.sections).mockReturnValue(new Promise((done) => { resolve = done; })); renderWithProviders(<ReportsPage />); expect(await screen.findByPlaceholderText("Loading section…")).toBeDisabled(); resolve(page([section])); expect(await screen.findByRole("combobox", { name: "Section" })).toBeEnabled(); });

  it("generates the report with selected internal IDs and readable print naming", async () => { currentParams = "report=section-timetable&academic_term_id=term-1&timetable_id=tt-1&version_id=version-active&resource_id=section-1"; renderWithProviders(<ReportsPage />); expect(await screen.findByText("Programming")).toBeInTheDocument(); expect(await screen.findByDisplayValue("2026-27 I-I • CSE-A")).toBeInTheDocument(); expect(timetableApi.viewGrid).toHaveBeenCalledWith("version-active", "section", "section-1"); await waitFor(() => expect(screen.getByRole("link", { name: /Open print view/i })).toHaveAttribute("href", expect.stringContaining("label=2026-27"))); expect(screen.getByRole("button", { name: /Export CSV/i })).toBeEnabled(); });
  it("renders every configured student group without a three-group ceiling", async () => {
    currentParams = "report=batch-timetable&academic_term_id=term-1&timetable_id=tt-1&version_id=version-active&section_id=section-1";
    vi.mocked(masterApi.studentBatches).mockResolvedValue(page(Array.from({ length: 6 }, (_, index) => ({ id: `batch-${index + 1}`, section_id: "section-1", batch_name: `A${index + 1}`, sequence_number: index + 1, student_count: 12, is_active: true }))));
    const user = userEvent.setup();
    renderWithProviders(<ReportsPage />);
    await user.click(await screen.findByRole("combobox", { name: "Student batch" }));
    const options = await screen.findByRole("listbox", { name: "Student batch options" });
    expect(options).toHaveTextContent("A1");
    expect(options).toHaveTextContent("A6");
    expect(options.querySelectorAll('[role="option"]')).toHaveLength(6);
  });
  it("renders a combined class once with all participating section labels", async () => {
    currentParams = "report=faculty-timetable&academic_term_id=term-1&timetable_id=tt-1&version_id=version-active&resource_id=faculty-1";
    vi.mocked(timetableApi.viewGrid).mockResolvedValue({ ...grid, view_type: "faculty", resource_id: "faculty-1", days: [{ ...grid.days[0], entries: [{ ...grid.days[0].entries[0], combined_teaching_event_id: "event-1", combined_teaching_group_code: "DS-CSE-AB", combined_section_codes: ["CSE-A", "CSE-B"], course_code: "CS301", course_name: "Data Structures", classroom_room_number: "1101", faculty_code: "VCE001" }] }] });
    renderWithProviders(<ReportsPage />);
    expect(await screen.findByText("Combined: CSE-A + CSE-B")).toBeInTheDocument();
    expect(screen.getAllByText("CS301")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Export CSV/i })).toBeEnabled();
  });
});
