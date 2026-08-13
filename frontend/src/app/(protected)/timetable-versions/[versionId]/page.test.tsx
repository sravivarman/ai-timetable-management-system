import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import VersionPage from "@/app/(protected)/timetable-versions/[versionId]/page";
import { entryOperationsApi, masterApi, timetableApi, versionOperationsApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("next/navigation", () => ({ useParams: () => ({ versionId: "version-1" }), useSearchParams: () => new URLSearchParams(), useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: (...roles: string[]) => roles.includes("Administrator") }) }));
vi.mock("@/lib/master-data-api", () => ({ masterDataApi: { lookup: vi.fn().mockResolvedValue([]) } }));
vi.mock("@/lib/api", () => ({
  timetableApi: { version: vi.fn(), get: vi.fn(), entries: vi.fn(), solverRuns: vi.fn(), conflicts: vi.fn(), sectionGrid: vi.fn(), viewGrid: vi.fn(), quality: vi.fn(), versions: vi.fn(), transition: vi.fn() },
  versionOperationsApi: { buildInput: vi.fn(), solverInput: vi.fn(), solve: vi.fn(), copy: vi.fn(), compare: vi.fn(), free: vi.fn() },
  masterApi: { workingDays: vi.fn(), classrooms: vi.fn(), laboratories: vi.fn() },
  entryOperationsApi: { move: vi.fn(), lock: vi.fn(), unlock: vi.fn(), audit: vi.fn() },
  validationApi: { get: vi.fn().mockRejectedValue(new Error("Unavailable in fixture")) },
}));

const now = "2026-08-03T12:00:00Z";
const version = { id: "version-1", timetable_id: "timetable-1", version_number: 3, version_name: "Published review", source_type: "MANUAL_COPY", validation_run_id: "validation-1", solver_status: "OPTIMAL", is_active: true, is_locked: true, created_by: "user", created_at: now, updated_at: now };
const timetable = { id: "timetable-1", academic_term_id: "term", scope_type: "SECTION", section_id: "section-1", name: "CSE I-I", status: "PUBLISHED", active_version_id: "version-1", created_by: "user", created_at: now, updated_at: now };
const entry = { id: "entry-1", timetable_version_id: "version-1", course_offering_id: "offering", section_id: "section-1", faculty_id: "faculty-1", classroom_id: "classroom-1", laboratory_id: null, student_batch_id: null, working_day_id: "day-1", period_number: 1, session_length: 1, entry_type: "THEORY", is_manual: false, is_locked: true };
const grid = { version_id: "version-1", view_type: "section", resource_id: "section-1", schedule_type: "HIGHER_YEAR", days: [{ working_day_id: "day-1", day_name: "Monday", sequence_number: 1, entries: [{ entry_id: "entry-1", working_day_id: "day-1", day_name: "Monday", period_number: 1, period_numbers: [1], schedule_type: "HIGHER_YEAR", start_time: "09:10:00", end_time: "10:10:00", course_code: "A9001", course_name: "Algorithms", course_type: "THEORY", section_code: "CSE-A", faculty_code: "VCE001", faculty_name: "Faculty A", classroom_room_number: "3204", laboratory_code: null, laboratory_name: null, batch_name: null, session_length: 1, entry_status: "LOCKED", is_manual: false, is_locked: true }] }] };
const snapshot = { id: "snapshot-1", timetable_version_id: "version-1", snapshot_json: { sections: [{}], course_offerings: [{}], faculty: [{}], classrooms: [{}], laboratories: [], locked_entries: [{}] }, input_hash: "abc123", created_at: now };

describe("Timetable version operational workspace", () => {
  it("keeps all read-only tools visible while locked mutations are disabled", async () => {
    vi.mocked(timetableApi.version).mockResolvedValue(version);
    vi.mocked(timetableApi.get).mockResolvedValue(timetable);
    vi.mocked(timetableApi.entries).mockResolvedValue({ items: [entry], total: 1, page: 1, page_size: 100, pages: 1 });
    vi.mocked(timetableApi.solverRuns).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, pages: 0 });
    vi.mocked(timetableApi.versions).mockResolvedValue({ items: [version], total: 1, page: 1, page_size: 100, pages: 1 });
    vi.mocked(timetableApi.sectionGrid).mockResolvedValue(grid);
    vi.mocked(timetableApi.viewGrid).mockResolvedValue(grid);
    vi.mocked(versionOperationsApi.solverInput).mockResolvedValue(snapshot);
    vi.mocked(masterApi.workingDays).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, pages: 0 });
    renderWithProviders(<VersionPage />);
    expect(await screen.findByText("Version metadata")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Rebuild solver input" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run solver" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy version" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Archive" })).toBeEnabled();
    expect(screen.getByText("abc123")).toBeInTheDocument();
    expect(screen.queryByText("snapshot-1")).not.toBeInTheDocument();
    for (const name of ["Section View", "Faculty View", "Classroom View", "Laboratory View", "Batch View", "Entries", "Solver Runs", "Quality", "Conflicts", "Comparison", "Free Resources"]) expect(screen.getByRole("button", { name })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Entries" }));
    expect(await screen.findByRole("button", { name: "Move" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Unlock" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Audit" })).toBeEnabled();
    expect(entryOperationsApi.move).not.toHaveBeenCalled();
  });
});
