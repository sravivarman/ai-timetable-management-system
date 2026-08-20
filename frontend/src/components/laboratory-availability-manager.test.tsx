import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LaboratoryAvailabilityManager } from "@/components/laboratory-availability-manager";
import { masterDataApi } from "@/lib/master-data-api";
import { api } from "@/lib/api-client";
import { renderWithProviders } from "@/test/render";
import { downloadCsv } from "@/lib/csv";

vi.mock("@/lib/master-data-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api");
  return { ...actual, masterDataApi: { ...actual.masterDataApi, lookup: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } };
});
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});
vi.mock("@/lib/csv",()=>({downloadCsv:vi.fn()}));

const lab = { id: "lab-1", laboratory_code: "LAB3201", laboratory_name: "Power Electronics Lab", room_number: "3201", owning_department_id: "dep-1", is_shareable_across_departments: true, availability_mode: "EXCEPT_BLOCKED", is_active: true };
const term = { id: "term-1", academic_year: "2026-27", term_name: "I-I", is_current: true, is_active: true };
const monday = { id: "day-1", day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true };

describe("laboratory availability manager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/laboratories" ? [lab] : endpoint === "/academic-terms" ? [term] : endpoint === "/working-days" ? [monday] : []);
    vi.mocked(api.get).mockImplementation(async (url) => ({ data: { items: url === "/resource-availability/profiles" ? [{ id: "profile-1", availability_mode: "EXCEPT_BLOCKED" }] : [] } }) as never);
    vi.mocked(api.post).mockResolvedValue({ data: { id: "slot-1" } });vi.mocked(api.put).mockResolvedValue({ data: {} });vi.mocked(api.delete).mockResolvedValue({ data: {} });
  });

  it("renders the weekly state and creates a blocked slot in EXCEPT_BLOCKED mode", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LaboratoryAvailabilityManager canManage initialLaboratoryId="lab-1" initialTermId="term-1" />);
    const cell = await screen.findByRole("button", { name: "Monday P1: Available" });
    await user.click(cell);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resource-availability/slots", expect.objectContaining({ resource_type: "LABORATORY", resource_id: "lab-1", academic_term_id: "term-1", working_day_id: "day-1", period_number: 1, availability_type: "BLOCKED" })));
  });

  it("shows selected-only slots as green and all other cells as unavailable", async () => {
    vi.mocked(api.get).mockImplementation(async (url) => ({ data: { items: url === "/resource-availability/profiles" ? [{ id: "profile-1", availability_mode: "ONLY_SELECTED" }] : [{ id: "slot-1", resource_type: "LABORATORY", resource_id: "lab-1", academic_term_id: "term-1", working_day_id: "day-1", period_number: 5, availability_type: "ALLOWED", is_active: true }] } }) as never);
    renderWithProviders(<LaboratoryAvailabilityManager initialLaboratoryId="lab-1" initialTermId="term-1" />);
    expect(await screen.findByRole("button", { name: "Monday P5: Available" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Monday P1: Unavailable" })).toBeDisabled();
  });

  it("renders the unrestricted default without persisting a missing profile", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [] } });
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/laboratories" ? [{ ...lab, availability_mode: "ALL_PERIODS" }] : endpoint === "/academic-terms" ? [term] : endpoint === "/working-days" ? [monday] : []);
    renderWithProviders(<LaboratoryAvailabilityManager canManage initialLaboratoryId="lab-1" initialTermId="term-1" />);
    expect(await screen.findByText("Availability not configured")).toBeInTheDocument();
    expect(screen.getByText("Available all instructional periods (default)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Configure Availability" })).toBeEnabled();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("does not query a profile without an academic term", async () => {
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/laboratories" ? [lab] : endpoint === "/working-days" ? [monday] : []);
    renderWithProviders(<LaboratoryAvailabilityManager initialLaboratoryId="lab-1" />);
    await waitFor(() => expect(masterDataApi.lookup).toHaveBeenCalledWith("/academic-terms", true));
    expect(api.get).not.toHaveBeenCalled();
  });

  it("does not query a profile without a resource", async () => {
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/academic-terms" ? [term] : endpoint === "/working-days" ? [monday] : []);
    renderWithProviders(<LaboratoryAvailabilityManager initialTermId="term-1" />);
    expect(await screen.findByText("Select a laboratory")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });

  it("exports the selected availability using business keys only", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LaboratoryAvailabilityManager canManage initialLaboratoryId="lab-1" initialTermId="term-1" />);
    await user.click(await screen.findByRole("button", { name: "Export availability CSV" }));
    expect(downloadCsv).toHaveBeenCalledWith("laboratory-availability", [expect.objectContaining({ resource_type: "LABORATORY", resource_code: "LAB3201", academic_term_code: "2026-27 | I-I" })]);
    const exported = vi.mocked(downloadCsv).mock.calls[0][1][0];
    expect(Object.keys(exported).some((key)=>key.endsWith("_id"))).toBe(false);
  });

  it("creates an exact-date exception with the selected readable resource context", async () => {
    vi.mocked(api.get).mockImplementation(async (url) => url === "/resource-availability/date-exceptions" ? ({ data: [] } as never) : ({ data: { items: url === "/resource-availability/profiles" ? [{ id: "profile-1", availability_mode: "EXCEPT_BLOCKED" }] : [] } } as never));
    const user = userEvent.setup();
    renderWithProviders(<LaboratoryAvailabilityManager canManage initialLaboratoryId="lab-1" initialTermId="term-1" />);
    await user.type(await screen.findByLabelText("Exception date"), "2026-09-18");
    await user.click(screen.getByRole("button", { name: "Add exception" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resource-availability/date-exceptions", expect.objectContaining({ resource_type: "LABORATORY", resource_id: "lab-1", academic_term_id: "term-1", exception_date: "2026-09-18", period_start: 1, period_end: 7, availability_status: "UNAVAILABLE" })));
  });

  it("keeps Report Viewer style read-only access free of exception write controls", async () => {
    vi.mocked(api.get).mockImplementation(async (url) => url === "/resource-availability/date-exceptions" ? ({ data: [] } as never) : ({ data: { items: url === "/resource-availability/profiles" ? [{ id: "profile-1", availability_mode: "EXCEPT_BLOCKED" }] : [] } } as never));
    renderWithProviders(<LaboratoryAvailabilityManager initialLaboratoryId="lab-1" initialTermId="term-1" />);
    await screen.findByText("Date-specific exceptions");
    expect(screen.queryByRole("button", { name: "Add exception" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download exception CSV template" })).not.toBeInTheDocument();
  });
});
