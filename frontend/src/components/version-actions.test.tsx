import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FreeResourcesPanel, VersionActions } from "@/components/version-actions";
import { masterApi, versionOperationsApi } from "@/lib/api";
import type { Timetable, TimetableVersion } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

const push = vi.fn();
const roleState = vi.hoisted(() => ({ value: "Administrator" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: (...roles: string[]) => roles.includes(roleState.value) }) }));
vi.mock("@/lib/api", () => ({
  versionOperationsApi: { buildInput: vi.fn(), solverInput: vi.fn(), solve: vi.fn(), copy: vi.fn(), free: vi.fn() },
  masterApi: { workingDays: vi.fn(), classrooms: vi.fn(), laboratories: vi.fn() },
}));

const version: TimetableVersion = { id: "version-1", timetable_id: "timetable-1", version_number: 1, version_name: "Initial", source_type: "GENERATED", validation_run_id: "run", solver_status: "NOT_STARTED", is_active: true, is_locked: false, created_by: "user", created_at: "2026-08-03T12:00:00Z", updated_at: "2026-08-03T12:00:00Z" };
const timetable: Timetable = { id: "timetable-1", academic_term_id: "term", scope_type: "SECTION", section_id: "section", name: "CSE timetable", status: "DRAFT", created_by: "user", created_at: "2026-08-03T12:00:00Z", updated_at: "2026-08-03T12:00:00Z" };
const snapshot = { id: "snapshot-1", timetable_version_id: version.id, snapshot_json: { sections: [{}], course_offerings: [{}, {}], faculty: [{}], classrooms: [], laboratories: [{}], locked_entries: [] }, input_hash: "abc123", created_at: "2026-08-03T12:00:00Z" };

describe("Version operational actions", () => {
  beforeEach(() => { roleState.value = "Administrator"; vi.spyOn(window, "confirm").mockReturnValue(true); vi.mocked(versionOperationsApi.solverInput).mockRejectedValue(new Error("No snapshot")); vi.mocked(versionOperationsApi.buildInput).mockResolvedValue(snapshot); push.mockReset(); });

  it("builds solver input and invalidates relevant queries", async () => {
    const { client } = renderWithProviders(<VersionActions version={version} timetable={timetable} />); const invalidate = vi.spyOn(client, "invalidateQueries"); const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Build solver input" }));
    await waitFor(() => expect(versionOperationsApi.buildInput).toHaveBeenCalledWith(version.id));
    expect(invalidate).toHaveBeenCalled();
  });

  it("submits solver configuration and displays the result", async () => {
    vi.mocked(versionOperationsApi.solve).mockResolvedValue({ id: "solver", timetable_version_id: version.id, solver_input_snapshot_id: "snapshot", status: "OPTIMAL", started_at: "now", runtime_seconds: 2, objective_value: 4, best_bound: 4, generated_entry_count: 12, statistics_json: { total_penalty: 1, quality_metrics: { quality_score: 99 } }, created_by: "user", created_at: "now" });
    renderWithProviders(<VersionActions version={version} timetable={timetable} />); const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Run solver" }));
    await user.click(screen.getAllByRole("button", { name: "Run solver" }).at(-1)!);
    expect(await screen.findByText("OPTIMAL")).toBeInTheDocument();
    expect(versionOperationsApi.solve).toHaveBeenCalledWith(version.id, expect.objectContaining({ optimization_profile: "BALANCED", random_seed: 1 }));
  });

  it("shows a rebuild instruction for a stale snapshot error", async () => {
    vi.mocked(versionOperationsApi.solve).mockRejectedValue(new Error("Solver input snapshot is stale"));
    renderWithProviders(<VersionActions version={version} timetable={timetable} />); const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Run solver" })); await user.click(screen.getAllByRole("button", { name: "Run solver" }).at(-1)!);
    expect((await screen.findAllByText("Solver input snapshot is stale")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Rebuild the solver input/)).toBeInTheDocument();
  });

  it("keeps locked-version controls visible but disables prohibited mutations", async () => {
    renderWithProviders(<VersionActions version={{ ...version, is_locked: true }} timetable={timetable} />);
    expect(screen.getByRole("button", { name: "Build solver input" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run solver" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy version" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Build solver input" })).toHaveAttribute("title", "Locked versions cannot rebuild solver input.");
    expect(await screen.findByText("No solver input snapshot")).toBeInTheDocument();
  });

  it("copies a version and navigates to the new version", async () => {
    vi.mocked(versionOperationsApi.copy).mockResolvedValue({ ...version, id: "version-copy", version_number: 2, source_type: "MANUAL_COPY" });
    renderWithProviders(<VersionActions version={version} timetable={timetable} />); const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Copy version" })); await user.click(screen.getAllByRole("button", { name: "Copy version" }).at(-1)!);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/timetable-versions/version-copy"));
  });

  it("gives HOD read-only solver-input access without coordinator mutations", async () => {
    roleState.value = "HOD";
    vi.mocked(versionOperationsApi.solverInput).mockResolvedValue(snapshot);
    renderWithProviders(<VersionActions version={version} timetable={timetable} />);
    expect(await screen.findByText("abc123")).toBeInTheDocument();
    expect(screen.queryByText("snapshot-1")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Build solver input|Rebuild solver input/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run solver" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy version" })).not.toBeInTheDocument();
    expect(screen.getByText("Your role has read-only access to this version.")).toBeInTheDocument();
  });

  it("queries free faculty, classrooms, and laboratories for the selected slot", async () => {
    vi.mocked(masterApi.workingDays).mockResolvedValue({ items: [{ id: "day-1", day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true }], total: 1, page: 1, page_size: 100, pages: 1 });
    vi.mocked(versionOperationsApi.free).mockImplementation(async (_id, kind) => ({ version_id: version.id, working_day_id: "day-1", period_number: 2, items: [{ id: `${kind}-1`, room_number: kind }] }));
    renderWithProviders(<FreeResourcesPanel versionId={version.id} />);
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Monday" });
    await user.selectOptions(screen.getByLabelText("Working day"), "day-1");
    await user.selectOptions(screen.getByLabelText("Period"), "2");
    await user.click(screen.getByRole("button", { name: "Find free resources" }));
    await waitFor(() => expect(versionOperationsApi.free).toHaveBeenCalledTimes(3));
    expect(versionOperationsApi.free).toHaveBeenCalledWith(version.id, "faculty", "day-1", 2);
    expect(versionOperationsApi.free).toHaveBeenCalledWith(version.id, "classrooms", "day-1", 2);
    expect(versionOperationsApi.free).toHaveBeenCalledWith(version.id, "laboratories", "day-1", 2);
  });
});
