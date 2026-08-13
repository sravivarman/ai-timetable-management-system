import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditDialog, EntryActions, MoveDialog, UnlockDialog } from "@/components/entry-actions";
import { entryOperationsApi, masterApi, versionOperationsApi } from "@/lib/api";
import type { TimetableEntry } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({
  entryOperationsApi: { move: vi.fn(), lock: vi.fn(), unlock: vi.fn(), audit: vi.fn() },
  masterApi: { workingDays: vi.fn(), classrooms: vi.fn(), laboratories: vi.fn() },
  versionOperationsApi: { solverInput: vi.fn() },
}));
const entry: TimetableEntry = { id: "entry-1", timetable_version_id: "version-1", course_offering_id: "offering", section_id: "section", faculty_id: "faculty", classroom_id: "classroom", working_day_id: "day-1", period_number: 1, session_length: 1, entry_type: "THEORY", is_manual: false, is_locked: false };
const page = { total: 1, page: 1, page_size: 100, pages: 1 };

describe("Entry operational actions", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(masterApi.workingDays).mockResolvedValue({ ...page, items: [{ id: "day-1", day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true }, { id: "day-2", day_name: "Tuesday", sequence_number: 2, is_working_day: true, is_active: true }] });
    vi.mocked(masterApi.classrooms).mockResolvedValue({ ...page, items: [{ id: "classroom", room_number: "101", room_name: "Main", is_active: true }] });
    vi.mocked(masterApi.laboratories).mockResolvedValue({ ...page, items: [{ id: "lab", laboratory_code: "CSE-LAB", laboratory_name: "Programming", room_number: "201", is_active: true }, { id: "chem", laboratory_code: "CHEM-LAB", laboratory_name: "Chemistry", room_number: "202", is_active: true }] });
    vi.mocked(versionOperationsApi.solverInput).mockResolvedValue({ id: "snapshot", timetable_version_id: "version-1", snapshot_json: { course_offerings: [{ id: "offering", eligible_laboratory_ids: ["lab"] }] }, input_hash: "hash", created_at: "2026-08-01T00:00:00Z" });
  });

  it("submits a valid manual move and preserves the entry session", async () => {
    vi.mocked(entryOperationsApi.move).mockResolvedValue({ ...entry, working_day_id: "day-2", period_number: 3, is_manual: true, is_locked: true });
    renderWithProviders(<MoveDialog entry={entry} versionId="version-1" sectionId="section" onClose={vi.fn()} onChanged={vi.fn()} />); const user = userEvent.setup();
    await screen.findByRole("option", { name: "Tuesday" });
    expect(await screen.findByRole("option", { name: "CSE-LAB · Programming" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "CHEM-LAB · Chemistry" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Target working day"), "day-2"); await user.selectOptions(screen.getByLabelText("Target period"), "3"); await user.click(screen.getByRole("button", { name: "Move entry" }));
    await waitFor(() => expect(entryOperationsApi.move).toHaveBeenCalledWith("entry-1", expect.objectContaining({ working_day_id: "day-2", period_number: 3, lock_after_move: true })));
  });

  it("shows the backend move conflict verbatim", async () => {
    vi.mocked(entryOperationsApi.move).mockRejectedValue(new Error("Overlapping timetable entry conflicts: faculty"));
    renderWithProviders(<MoveDialog entry={entry} versionId="version-1" onClose={vi.fn()} onChanged={vi.fn()} />); const user = userEvent.setup(); await user.click(screen.getByRole("button", { name: "Move entry" }));
    expect(await screen.findByText("Overlapping timetable entry conflicts: faculty")).toBeInTheDocument();
  });

  it("locks an editable entry after confirmation", async () => {
    vi.mocked(entryOperationsApi.lock).mockResolvedValue({ ...entry, is_locked: true });
    renderWithProviders(<EntryActions entry={entry} versionId="version-1" editable />); const user = userEvent.setup(); await user.click(screen.getByRole("button", { name: "Lock" }));
    await waitFor(() => expect(entryOperationsApi.lock).toHaveBeenCalledWith("entry-1"));
  });

  it("requires a nonblank unlock reason before submission", async () => {
    vi.mocked(entryOperationsApi.unlock).mockResolvedValue({ ...entry, is_locked: false });
    renderWithProviders(<UnlockDialog entry={{ ...entry, is_locked: true }} onClose={vi.fn()} onChanged={vi.fn()} />); const user = userEvent.setup(); const button = screen.getByRole("button", { name: "Unlock entry" }); expect(button).toBeDisabled(); await user.type(screen.getByLabelText("Reason"), "Correct faculty assignment"); expect(button).toBeEnabled(); await user.click(button);
    await waitFor(() => expect(entryOperationsApi.unlock).toHaveBeenCalledWith("entry-1", "Correct faculty assignment"));
  });

  it("renders the chronological audit timeline and value diff", async () => {
    vi.mocked(entryOperationsApi.audit).mockResolvedValue([{ id: "audit", timetable_entry_id: "entry-1", timetable_version_id: "version-1", action_type: "MOVED", old_values_json: { period_number: 1 }, new_values_json: { period_number: 3 }, reason: "Resolve clash", performed_by: "user", created_at: "2026-08-03T12:00:00Z" }]);
    renderWithProviders(<AuditDialog entryId="entry-1" onClose={vi.fn()} />);
    expect(await screen.findByText("MOVED")).toBeInTheDocument(); expect(screen.getByText("Reason: Resolve clash")).toBeInTheDocument(); expect(screen.getAllByText("period number")).toHaveLength(2);
  });

  it("keeps review actions discoverable when version safeguards disable mutations", () => {
    renderWithProviders(<EntryActions entry={entry} versionId="version-1" editable disabledReason="This version is locked." canAudit />);
    expect(screen.getByRole("button", { name: "Move" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Lock" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Audit" })).toBeEnabled();
  });
});
