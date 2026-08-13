import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MasterDataDashboard from "@/app/(protected)/master-data/page";
import { masterDataApi } from "@/lib/master-data-api";
import { validationApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/master-data-api", async () => { const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api"); return { ...actual, masterDataApi: { ...actual.masterDataApi, list: vi.fn() } }; });
vi.mock("@/lib/api", () => ({ validationApi: { list: vi.fn() } }));

describe("master-data dashboard", () => {
  it("shows operational counts and links to every grouped module", async () => {
    vi.mocked(masterDataApi.list).mockResolvedValue({ items: [], total: 7, page: 1, page_size: 1, pages: 7 });
    vi.mocked(validationApi.list).mockResolvedValue({ items: [], total: 2, page: 1, page_size: 1, pages: 2 });
    renderWithProviders(<MasterDataDashboard />);
    expect(await screen.findByRole("link", { name: /7 Departments/ })).toHaveAttribute("href", "/master-data/departments");
    expect(screen.getByRole("link", { name: /2 Validation warnings/ })).toHaveAttribute("href", "/validation?status=WARNING");
    expect(screen.getByRole("link", { name: "Faculty Scheduling Policies" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Laboratory Configuration" })).toHaveAttribute("href", "/master-data/laboratory-configuration?variant=batch-configurations");
  });
});
