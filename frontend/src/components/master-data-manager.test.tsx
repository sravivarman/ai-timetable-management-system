import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { MasterDataManager } from "@/components/master-data-manager";
import { masterDataApi } from "@/lib/master-data-api";
import { masterConfigs } from "@/lib/master-data-config";
import { renderWithProviders } from "@/test/render";
import { queryKeys } from "@/lib/query-keys";
import { getResourceAvailabilityProfile } from "@/lib/resource-availability-api";
import { downloadCsv } from "@/lib/csv";

const state = vi.hoisted(() => ({ manage: true }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ user: { roles: state.manage ? [{ name: "Administrator", permissions: [] }] : [{ name: "Dean", permissions: [] }] }, hasRole: (...roles: string[]) => state.manage && roles.includes("Administrator") }) }));
vi.mock("@/lib/master-data-api", async () => { const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api"); return { ...actual, masterDataApi: { ...actual.masterDataApi, list: vi.fn(), lookup: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), restore: vi.fn(), all: vi.fn(), generateBatches: vi.fn() } }; });
vi.mock("@/lib/resource-availability-api",()=>({getResourceAvailabilityProfile:vi.fn(),getResourceAvailabilitySlots:vi.fn()}));
vi.mock("@/lib/csv",()=>({downloadCsv:vi.fn()}));

const page = { items: [
  { id: "d2", department_code: "EEE", department_name: "Electrical", short_name: "EEE", is_active: true },
  { id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true },
], total: 22, page: 1, page_size: 20, pages: 2 };

describe("master-data manager", () => {
  beforeEach(() => { state.manage = true; vi.clearAllMocks(); vi.mocked(masterDataApi.list).mockResolvedValue(page); vi.mocked(masterDataApi.lookup).mockResolvedValue([]); vi.mocked(masterDataApi.all).mockResolvedValue(page.items); });

  it("supports search, sorting, pagination, filters, and manage actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MasterDataManager config={masterConfigs.departments} module="departments" />);
    expect(await screen.findByText("Electrical")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search Departments"), "Computer");
    expect(screen.getByText("Computer Science")).toBeInTheDocument();
    expect(screen.queryByText("Electrical")).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search Departments"));
    await user.click(screen.getByRole("button", { name: "Code ↑" }));
    const dataRows = screen.getAllByRole("row").slice(1);
    expect(within(dataRows[0]).getAllByText("EEE")).toHaveLength(2);
    await user.selectOptions(screen.getByLabelText("Status filter"), "inactive");
    await waitFor(() => expect(masterDataApi.list).toHaveBeenLastCalledWith(masterConfigs.departments, expect.objectContaining({ is_active: false })));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(masterDataApi.list).toHaveBeenLastCalledWith(masterConfigs.departments, expect.objectContaining({ page: 2 })));
  });

  it("renders a read-only experience when manage permission is absent", async () => {
    state.manage = false;
    renderWithProviders(<MasterDataManager config={masterConfigs.departments} module="departments" />);
    expect(await screen.findByText("Electrical")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import CSV/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Duplicate" })).not.toBeInTheDocument();
  });

  it("uses Activity Faculty Allocations terminology", async () => {
    vi.mocked(masterDataApi.list).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    renderWithProviders(<MasterDataManager config={masterConfigs["laboratory-allocations"]} module="faculty-allocations" variant="laboratory" />);
    expect(await screen.findByRole("heading", { name: "Activity Faculty Allocations" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Theory Faculty Allocations" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Activity Faculty Allocations" })).toHaveAttribute("href", "/master-data/faculty-allocations?variant=laboratory");
    expect(screen.getByText(/laboratory and practical activities, including grouped and rotational sessions/i)).toBeInTheDocument();
  });

  it("activates the selected academic term, clears the previous current term, and refreshes dependent queries", async () => {
    const oldTerm = { id: "term-old", academic_year: "2025-26", term_name: "I-I", year_number: 1, semester_number: 1, start_date: "2025-08-01", end_date: "2025-12-20", is_active: true, is_current: true, is_first_year_term: true };
    const newTerm = { id: "term-new", academic_year: "2026-27", term_name: "II-I", year_number: 2, semester_number: 1, start_date: "2026-07-01", end_date: "2026-11-30", is_active: true, is_current: false, is_first_year_term: false };
    let terms = [oldTerm, newTerm];
    vi.mocked(masterDataApi.list).mockImplementation(async () => ({ items: terms, total: terms.length, page: 1, page_size: 20, pages: 1 }));
    vi.mocked(masterDataApi.update).mockImplementation(async (_config, id, payload) => {
      terms = terms.map((term) => term.id === id ? { ...term, ...payload } : term);
      return terms.find((term) => term.id === id)!;
    });
    const invalidate = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    const user = userEvent.setup();
    renderWithProviders(<MasterDataManager config={masterConfigs["academic-terms"]} module="academic-terms" />);

    const oldRow = (await screen.findByText("2025-26")).closest("tr")!;
    const newRow = screen.getByText("2026-27").closest("tr")!;
    expect(within(oldRow).getAllByText("ACTIVE").length).toBeGreaterThan(0);
    expect(within(oldRow).queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
    await user.click(within(newRow).getByRole("button", { name: "Activate" }));

    await waitFor(() => expect(masterDataApi.update).toHaveBeenCalledWith(masterConfigs["academic-terms"], "term-new", { is_active: true, is_current: true }));
    expect(masterDataApi.update).toHaveBeenCalledWith(masterConfigs["academic-terms"], "term-old", { is_current: false });
    await waitFor(() => {
      const activatedRow = screen.getByText("2026-27").closest("tr")!;
      const previousRow = screen.getByText("2025-26").closest("tr")!;
      expect(within(activatedRow).getAllByText("ACTIVE").length).toBeGreaterThan(0);
      expect(within(activatedRow).queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
      expect(within(previousRow).queryByText("ACTIVE")).not.toBeInTheDocument();
      expect(within(previousRow).getByRole("button", { name: "Activate" })).toBeEnabled();
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["master-data", "academic-terms"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.academicTerms });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.dashboard });
    invalidate.mockRestore();
  });

  it("generates and previews an arbitrary number of student groups", async () => {
    vi.mocked(masterDataApi.list).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    vi.mocked(masterDataApi.lookup).mockResolvedValue([{ id: "section-1", section_code: "CSE-A", section_name: "A", academic_term_id: "term-1", display_label: "2026-27 I-I • CSE-A", student_strength: 72, is_active: true }]);
    vi.mocked(masterDataApi.generateBatches).mockResolvedValue([]);
    const user = userEvent.setup();
    renderWithProviders(<MasterDataManager config={masterConfigs["student-batches"]} module="student-batches" />);

    await user.click(await screen.findByRole("button", { name: "Generate student groups" }));
    await user.click(screen.getByRole("combobox", { name: "Section" }));
    await user.click(within(await screen.findByRole("listbox", { name: "Section options" })).getByRole("option", { name: "2026-27 I-I • CSE-A" }));
    const count = screen.getByRole("spinbutton", { name: "Number of Student Groups" });
    await user.clear(count);
    await user.type(count, "6");

    expect(screen.getByLabelText("Generated group preview")).toHaveTextContent("A6");
    expect(screen.getByLabelText("Generated group preview")).toHaveTextContent("12 students");
    await user.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() => expect(masterDataApi.generateBatches).toHaveBeenCalledWith({ section_id: "section-1", number_of_groups: 6, naming_pattern: "{section}{sequence}", overwrite: false }));
  });

  it("does not preload classroom availability on the Sections page", async () => {
    vi.mocked(masterDataApi.list).mockResolvedValue({items:[],total:0,page:1,page_size:20,pages:0});
    renderWithProviders(<MasterDataManager config={masterConfigs.sections} module="sections"/>);
    expect(await screen.findByText("No sections found")).toBeInTheDocument();
    expect(getResourceAvailabilityProfile).not.toHaveBeenCalled();
  });

  it("renders contextual laboratory assignment values for course offerings", async () => {
    const courses = [
      { id: "course-theory", course_code: "A9001", course_name: "Matrices and Calculus", course_type: "THEORY", venue_requirement: "CLASSROOM_ONLY" },
      { id: "course-practical", course_code: "P1001", course_name: "Workshop", course_type: "PRACTICAL", venue_requirement: "CLASSROOM_ONLY" },
      { id: "course-open", course_code: "P1002", course_name: "Field Project", course_type: "PROJECT", venue_requirement: "NO_FIXED_VENUE" },
      { id: "course-auto", course_code: "L1001", course_name: "Automatic Lab", course_type: "LABORATORY", venue_requirement: "LABORATORY_ONLY" },
      { id: "course-preferred", course_code: "L1002", course_name: "Preferred Lab", course_type: "LABORATORY", venue_requirement: "LABORATORY_ONLY" },
      { id: "course-fixed", course_code: "L1003", course_name: "Required Lab", course_type: "LABORATORY", venue_requirement: "LABORATORY_ONLY" },
      { id: "course-restricted", course_code: "L1004", course_name: "Restricted Lab", course_type: "LABORATORY", venue_requirement: "LABORATORY_ONLY" },
    ];
    const offerings = courses.map((course, index) => ({ id: `offering-${index}`, course_id: course.id, section_id: "section-1", academic_term_id: "term-1", laboratory_selection_mode: index === 4 ? "PREFERRED" : index === 5 ? "FIXED" : index === 6 ? "RESTRICTED" : "AUTO", laboratory_override_id: index === 4 || index === 5 ? "laboratory-1" : null, allowed_laboratory_ids: index === 6 ? ["laboratory-1", "laboratory-2"] : [], is_mandatory: true, is_active: true }));
    vi.mocked(masterDataApi.list).mockResolvedValue({ items: offerings, total: offerings.length, page: 1, page_size: 20, pages: 1 });
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/courses" ? courses : endpoint === "/sections" ? [{ id: "section-1", display_label: "2026-27 I-I • CIV-A" }] : endpoint === "/academic-terms" ? [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }] : endpoint === "/laboratories" ? [{ id: "laboratory-1", laboratory_code: "GRAPHICS-1", laboratory_name: "Graphics Lab 1" }, { id: "laboratory-2", laboratory_code: "GRAPHICS-2", laboratory_name: "Graphics Lab 2" }] : []);
    renderWithProviders(<MasterDataManager config={masterConfigs["course-offerings"]} module="course-offerings" />);
    const rowForCourse = (pattern: RegExp) => screen.getAllByText(pattern).find((element) => element.tagName === "TD")!.closest("tr")!;
    await screen.findAllByText(/A9001.*Matrices and Calculus/);
    const theoryRow = rowForCourse(/A9001.*Matrices and Calculus/);
    expect(within(theoryRow).getAllByRole("cell")[5]).toHaveTextContent("—"); expect(within(theoryRow).getAllByRole("cell")[6]).toHaveTextContent("—");
    const practicalCells = within(rowForCourse(/P1001.*Workshop/)).getAllByRole("cell"); expect(practicalCells[5]).toHaveTextContent("—"); expect(practicalCells[6]).toHaveTextContent("—");
    const openCells = within(rowForCourse(/P1002.*Field Project/)).getAllByRole("cell"); expect(openCells[5]).toHaveTextContent("—"); expect(openCells[6]).toHaveTextContent("—");
    expect(within(rowForCourse(/L1001.*Automatic Lab/)).getByText("Automatic")).toBeInTheDocument();
    expect(within(rowForCourse(/L1001.*Automatic Lab/)).getByText("Any eligible laboratory")).toBeInTheDocument();
    expect(within(rowForCourse(/L1002.*Preferred Lab/)).getByText("Preferred")).toBeInTheDocument();
    expect(within(rowForCourse(/L1003.*Required Lab/)).getByText("Required")).toBeInTheDocument();
    expect(within(rowForCourse(/L1004.*Restricted Lab/)).getByText("Restricted")).toBeInTheDocument();
    expect(within(rowForCourse(/L1004.*Restricted Lab/)).getByText(/GRAPHICS-1.*GRAPHICS-2/)).toBeInTheDocument();
    expect(screen.getAllByText(/GRAPHICS-1.*Graphics Lab 1/)).toHaveLength(3);
    expect(document.body).not.toHaveTextContent("laboratory-1");
  });

  it("uses the same readable-key serializer for filtered and entire-dataset exports", async () => {
    const course = { id: "course-id", course_code: "CS301", course_name: "Operating Systems", offering_department_id: "department-id", eligible_laboratory_ids: ["laboratory-id"], default_laboratory_id: "laboratory-id", course_type: "THEORY", weekly_periods: 4, counts_toward_workload: true, is_active: true };
    vi.mocked(masterDataApi.list).mockResolvedValue({ items: [course], total: 1, page: 1, page_size: 20, pages: 1 });
    vi.mocked(masterDataApi.all).mockResolvedValue([course]);
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [{ id: "department-id", department_code: "CSE", is_active: true }] : endpoint === "/laboratories" ? [{ id: "laboratory-id", laboratory_code: "CSE-LAB-01", is_active: true }] : []);
    const user = userEvent.setup();
    renderWithProviders(<MasterDataManager config={masterConfigs.courses} module="courses" />);
    expect(await screen.findByText("Operating Systems")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Export current filter" }));
    await waitFor(() => expect(downloadCsv).toHaveBeenCalledWith("courses-filtered", [expect.objectContaining({ course_code: "CS301", offering_department_code: "CSE", eligible_laboratory_codes: "CSE-LAB-01", preferred_laboratory_code: "CSE-LAB-01" })]));
    const filteredRows = vi.mocked(downloadCsv).mock.calls.at(-1)?.[1];

    await user.click(screen.getByRole("button", { name: "Export entire dataset" }));
    await waitFor(() => expect(downloadCsv).toHaveBeenCalledWith("courses-all", filteredRows));
  });
});
