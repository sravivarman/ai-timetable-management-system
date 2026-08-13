import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(protected)/dashboard/page";
import { listAcademicTerms, solverApi, timetableApi, validationApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  listAcademicTerms: vi.fn(), solverApi: { list: vi.fn() }, validationApi: { list: vi.fn() },
  timetableApi: { list: vi.fn(), conflicts: vi.fn(), history: vi.fn() },
}));
const emptyPage = { items: [], total: 0, page: 1, page_size: 1, pages: 0 };

describe("Operational dashboard", () => {
  beforeEach(() => {
    vi.mocked(listAcademicTerms).mockResolvedValue({ ...emptyPage, items: [{ id: "term", academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }] });
    vi.mocked(timetableApi.list).mockResolvedValue({ ...emptyPage, items: [] });
    vi.mocked(validationApi.list).mockResolvedValue({ ...emptyPage, total: 1, pages: 1, items: [{ id: "validation", academic_term_id: "term", scope_type: "COLLEGE", status: "PASSED", total_checks: 1, passed_checks: 1, failed_checks: 0, warning_checks: 0, started_at: "2026-08-03T12:00:00Z", completed_at: "2026-08-03T12:00:00Z", created_by: "user", created_at: "2026-08-03T12:00:00Z" }] });
  });
  it("renders counts, validation, solver quality, and runtime widgets", async () => {
    vi.mocked(solverApi.list).mockResolvedValue({ ...emptyPage, total: 1, pages: 1, items: [{ id: "run-1", timetable_version_id: "version-1", solver_input_snapshot_id: "snapshot-1", status: "OPTIMAL", started_at: "2026-08-03T11:59:00Z", runtime_seconds: 2.4, objective_value: 10, generated_entry_count: 42, created_at: "2026-08-03T12:00:00Z", created_by: "user-1", statistics_json: { optimization_profile: "QUALITY", quality_metrics: { quality_score: 98.5 } } }] });
    renderDashboard();
    expect(await screen.findByText("OPTIMAL")).toBeInTheDocument();
    expect(screen.getByText("Profile QUALITY · Quality 98.5 · Runtime 2.40s")).toBeInTheDocument();
    expect(screen.getByText("Average quality")).toBeInTheDocument(); expect(screen.getByText("Active versions")).toBeInTheDocument(); expect(screen.getByText("Recent workflow actions")).toBeInTheDocument();
    expect(solverApi.list).toHaveBeenCalledWith({ page: 1, page_size: 1 });
  });
  it("shows no runs only when the global list is empty", async () => { vi.mocked(solverApi.list).mockResolvedValue(emptyPage); renderDashboard(); expect(await screen.findByText("No runs")).toBeInTheDocument(); await waitFor(() => expect(solverApi.list).toHaveBeenCalled()); });
});
function renderDashboard() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>); }
