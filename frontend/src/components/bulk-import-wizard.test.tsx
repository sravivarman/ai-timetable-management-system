import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BulkImportWizard } from "@/components/bulk-import-wizard";
import { masterDataApi } from "@/lib/master-data-api";
import { masterConfigs } from "@/lib/master-data-config";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/master-data-api", async () => { const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api"); return { ...actual, masterDataApi: { ...actual.masterDataApi, create: vi.fn(), update: vi.fn(), lookup: vi.fn(), all: vi.fn() } }; });

describe("bulk import wizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(masterDataApi.lookup).mockResolvedValue([]);
    vi.mocked(masterDataApi.all).mockResolvedValue([]);
  });

  it("previews, validates, imports, and summarizes CSV rows", async () => {
    vi.mocked(masterDataApi.create).mockResolvedValue({ id: "d1" });
    const complete = vi.fn(); const user = userEvent.setup();
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={complete} />);
    const file = new File(["department_code,department_name,short_name\nCSE,Computer Science,CSE"], "departments.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve("department_code,department_name,short_name\nCSE,Computer Science,CSE") });
    await user.upload(screen.getByLabelText("CSV file"), file);
    expect(await screen.findByText(/1 rows detected/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Validate" }));
    expect(screen.getByText(/passed readable-key resolution/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import rows" }));
    expect(await screen.findByText("Inserted")).toBeInTheDocument();
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.departments, expect.objectContaining({ department_code: "CSE" }));
    expect(complete).toHaveBeenCalled();
  });

  it("shows validation errors and skips invalid rows during import", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BulkImportWizard config={masterConfigs.departments} onClose={vi.fn()} onComplete={vi.fn()} />);
    const csv = "department_code,department_name,short_name\n,Missing code,CSE"; const file = new File([csv], "invalid.csv", { type: "text/csv" }); Object.defineProperty(file, "text", { value: () => Promise.resolve(csv) });
    await user.upload(screen.getByLabelText("CSV file"), file); await user.click(await screen.findByRole("button", { name: "Validate" }));
    expect(screen.getAllByText(/Department code is required/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Import rows" }));
    expect(await screen.findByText("Skipped")).toBeInTheDocument();
  });

  it("imports faculty records without a user account link", async () => {
    vi.mocked(masterDataApi.create).mockResolvedValue({ id: "faculty-1" });
    vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => endpoint === "/departments" ? [{ id: "department-1", department_code: "CSE", department_name: "Computer Science", is_active: true }] : []);
    const user = userEvent.setup();
    renderWithProviders(<BulkImportWizard config={masterConfigs.faculty} onClose={vi.fn()} onComplete={vi.fn()} />);
    const csv = "faculty_code,full_name,department_code,designation,institutional_email,minimum_weekly_workload,maximum_weekly_workload\nVCE042,Dr R Kumar,CSE,Professor,kumar@vce.ac.in,0,18";
    const file = new File([csv], "faculty.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve(csv) });
    await user.upload(screen.getByLabelText("CSV file"), file);
    await user.click(await screen.findByRole("button", { name: "Validate" }));
    await user.click(screen.getByRole("button", { name: "Import rows" }));
    await screen.findByText("Inserted");
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.faculty, expect.objectContaining({ department_id: "department-1" }));
    expect(masterDataApi.create).toHaveBeenCalledWith(masterConfigs.faculty, expect.not.objectContaining({ user_id: expect.anything() }));
  });
});
