import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BulkImportWizard } from "@/components/bulk-import-wizard";
import { masterDataApi } from "@/lib/master-data-api";
import { masterConfigs } from "@/lib/master-data-config";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/master-data-api", async () => { const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api"); return { ...actual, masterDataApi: { ...actual.masterDataApi, create: vi.fn(), update: vi.fn(), get: vi.fn(), remove: vi.fn(), restore: vi.fn(), lookup: vi.fn(), all: vi.fn() } }; });

async function upload(csv: string, name = "import.csv") {
  const file = new File([csv], name, { type: "text/csv" });
  Object.defineProperty(file, "text", { value: () => Promise.resolve(csv) });
  await userEvent.upload(screen.getByLabelText("CSV file"), file);
}

describe("safe bulk import wizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(masterDataApi.lookup).mockResolvedValue([]);
    vi.mocked(masterDataApi.all).mockResolvedValue([]);
  });

  it("previews classifications before creating only NEW rows", async () => {
    vi.mocked(masterDataApi.create).mockResolvedValue({ id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true });
    const complete = vi.fn(); const user = userEvent.setup();
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={complete} />);
    await upload("department_code,department_name,short_name\nCSE,Computer Science,CSE", "departments.csv");
    expect(await screen.findByText("NEW")).toBeInTheDocument();
    expect(masterDataApi.create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Create 1 New Records" }));
    expect(await screen.findByText("CREATED")).toBeInTheDocument();
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.departments, expect.objectContaining({ department_code: "CSE" }));
    expect(masterDataApi.update).not.toHaveBeenCalled();
    expect(complete).toHaveBeenCalled();
  });

  it("shows invalid rows without writing them", async () => {
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={vi.fn()} />);
    await upload("department_code,department_name,short_name\n,Missing code,CSE");
    expect(await screen.findByText("INVALID")).toBeInTheDocument();
    expect(screen.getByText(/Department code is required/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue to Review" }));
    expect(masterDataApi.create).not.toHaveBeenCalled();
    expect(masterDataApi.update).not.toHaveBeenCalled();
  });

  it("does not silently update CHANGED rows and supports Keep Existing", async () => {
    const existing = { id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true, updated_at: "2026-01-01T00:00:00Z" };
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [existing] : []);
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={vi.fn()} />);
    await upload("department_code,department_name,short_name\nCSE,Computer Science and Engineering,CSE");
    expect(await screen.findByText("CHANGED")).toBeInTheDocument();
    expect(masterDataApi.update).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Continue to Review" }));
    const article = screen.getByText(/Row 2:/).closest("article")!;
    expect(within(article).getByText("Computer Science")).toBeInTheDocument();
    expect(within(article).getByText("Computer Science and Engineering")).toBeInTheDocument();
    await userEvent.click(within(article).getByRole("button", { name: "Keep Existing" }));
    expect(within(article).getByText("KEPT EXISTING")).toBeInTheDocument();
    expect(masterDataApi.update).not.toHaveBeenCalled();
  });

  it("updates a CHANGED row only after approval and sends its timestamp baseline", async () => {
    const existing = { id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true, updated_at: "2026-01-01T00:00:00Z" };
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [existing] : []);
    vi.mocked(masterDataApi.get).mockResolvedValue(existing);
    vi.mocked(masterDataApi.update).mockResolvedValue({ ...existing, department_name: "Computer Science and Engineering", updated_at: "2026-01-02T00:00:00Z" });
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={vi.fn()} />);
    await upload("department_code,department_name,short_name\nCSE,Computer Science and Engineering,CSE");
    await userEvent.click(await screen.findByRole("button", { name: "Continue to Review" }));
    await userEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(await screen.findByText("UPDATED")).toBeInTheDocument();
    expect(masterDataApi.update).toHaveBeenCalledWith(masterConfigs.departments, "d1", expect.objectContaining({ department_name: "Computer Science and Engineering" }), "2026-01-01T00:00:00Z");
  });

  it("surfaces a stale preview as CONFLICT instead of overwriting", async () => {
    const baseline = { id: "d1", department_code: "CSE", department_name: "Computer Science", short_name: "CSE", is_active: true, updated_at: "2026-01-01T00:00:00Z" };
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [baseline] : []);
    vi.mocked(masterDataApi.get).mockResolvedValue({ ...baseline, department_name: "Computer Engineering", updated_at: "2026-01-03T00:00:00Z" });
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={vi.fn()} />);
    await upload("department_code,department_name,short_name\nCSE,Computer Science and Engineering,CSE");
    await userEvent.click(await screen.findByRole("button", { name: "Continue to Review" }));
    await userEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(await screen.findByText("CONFLICT")).toBeInTheDocument();
    expect(screen.getByText(/Record changed since import preview/)).toBeInTheDocument();
    expect(masterDataApi.update).not.toHaveBeenCalled();
  });

  it("imports faculty without a user account link", async () => {
    vi.mocked(masterDataApi.create).mockResolvedValue({ id: "faculty-1" });
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [{ id: "department-1", department_code: "CSE", department_name: "Computer Science", is_active: true }] : []);
    renderWithProviders(<BulkImportWizard config={masterConfigs.faculty} onClose={vi.fn()} onComplete={vi.fn()} />);
    await upload("faculty_code,full_name,department_code,designation,institutional_email,minimum_weekly_workload,maximum_weekly_workload\nVCE042,Dr R Kumar,CSE,Professor,kumar@vce.ac.in,0,18");
    await userEvent.click(await screen.findByRole("button", { name: "Create 1 New Records" }));
    await screen.findByText("CREATED");
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.faculty, expect.objectContaining({ department_id: "department-1" }));
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.faculty, expect.not.objectContaining({ user_id: expect.anything() }));
  });
});
