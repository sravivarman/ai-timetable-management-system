import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ComparisonPanel } from "@/components/comparison-panel";
import { timetableApi, versionOperationsApi } from "@/lib/api";
import type { TimetableVersion } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({ timetableApi: { versions: vi.fn() }, versionOperationsApi: { compare: vi.fn() } }));
const version: TimetableVersion = { id: "version-2", timetable_id: "tt", version_number: 2, source_type: "MANUAL_COPY", validation_run_id: "run", solver_status: "STALE", is_active: true, is_locked: false, created_by: "user", created_at: "now", updated_at: "now" };

describe("Version comparison", () => {
  it("renders comparison summary and old/new move slots", async () => {
    vi.mocked(timetableApi.versions).mockResolvedValue({ items: [{ ...version, id: "version-1", version_number: 1 }], total: 1, page: 1, page_size: 100, pages: 1 });
    vi.mocked(versionOperationsApi.compare).mockResolvedValue({ version_id: "version-2", other_version_id: "version-1", added_entries: [], removed_entries: [], moved_entries: [{ from: { day_name: "Monday", period_number: 1, course_code: "A9001", section_code: "CSE-A" }, to: { day_name: "Tuesday", period_number: 3, course_code: "A9001", section_code: "CSE-A" } }], faculty_changes: [], facility_changes: [], lock_state_changes: [], summary: { added: 0, removed: 0, moved: 1 } });
    renderWithProviders(<ComparisonPanel version={version} />); const user = userEvent.setup();
    await screen.findByRole("option", { name: /Version 1/ });
    await user.selectOptions(screen.getByLabelText("Compare with version"), "version-1");
    expect(await screen.findByText("Moved entries")).toBeInTheDocument(); expect(screen.getByText("Monday")).toBeInTheDocument(); expect(screen.getByText("Tuesday")).toBeInTheDocument(); expect(screen.getAllByText("A9001")).toHaveLength(2);
  });
});
