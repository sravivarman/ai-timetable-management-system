import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TimetableDetailPage from "@/app/(protected)/timetables/[timetableId]/page";
import { timetableApi } from "@/lib/api";
import type { Timetable } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

let roleNames: string[] = [];
vi.mock("next/navigation", () => ({ useParams: () => ({ timetableId: "tt-1" }) }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: (...roles: string[]) => roles.some((role) => roleNames.includes(role)) }) }));
vi.mock("@/lib/api", () => ({ timetableApi: { get: vi.fn(), versions: vi.fn(), history: vi.fn(), transition: vi.fn() } }));
const base: Timetable = { id: "tt-1", academic_term_id: "term", scope_type: "COLLEGE", name: "College timetable", status: "GENERATED", active_version_id: "version", created_by: "user", created_at: "2026-08-03T12:00:00Z", updated_at: "2026-08-03T12:00:00Z" };

describe("Timetable workflow controls", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(true); vi.spyOn(window, "prompt").mockReturnValue("Needs correction");
    vi.mocked(timetableApi.versions).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, pages: 0 }); vi.mocked(timetableApi.history).mockResolvedValue([]); vi.mocked(timetableApi.transition).mockResolvedValue(base);
  });

  it("submits a generated timetable for review and invalidates workflow queries", async () => {
    roleNames = ["Timetable Coordinator"]; vi.mocked(timetableApi.get).mockResolvedValue(base); const { client } = renderWithProviders(<TimetableDetailPage />); const invalidate = vi.spyOn(client, "invalidateQueries"); const user = userEvent.setup(); await user.click(await screen.findByRole("button", { name: "Submit for review" }));
    await waitFor(() => expect(timetableApi.transition).toHaveBeenCalledWith("tt-1", "submit-review", {})); expect(invalidate).toHaveBeenCalled();
  });

  it("allows Dean approval and Principal publication", async () => {
    roleNames = ["Dean"]; vi.mocked(timetableApi.get).mockResolvedValue({ ...base, status: "UNDER_REVIEW" }); const first = renderWithProviders(<TimetableDetailPage />); const user = userEvent.setup(); await user.click(await screen.findByRole("button", { name: "Approve" })); await waitFor(() => expect(timetableApi.transition).toHaveBeenCalledWith("tt-1", "approve", {})); first.unmount();
    vi.clearAllMocks(); roleNames = ["Principal"]; vi.mocked(timetableApi.get).mockResolvedValue({ ...base, status: "APPROVED" }); vi.mocked(timetableApi.versions).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, pages: 0 }); vi.mocked(timetableApi.history).mockResolvedValue([]); vi.mocked(timetableApi.transition).mockResolvedValue(base); renderWithProviders(<TimetableDetailPage />); await user.click(await screen.findByRole("button", { name: "Publish" })); await waitFor(() => expect(timetableApi.transition).toHaveBeenCalledWith("tt-1", "publish", {}));
  });

  it("requires and sends a return-to-draft reason", async () => {
    roleNames = ["Timetable Coordinator"]; vi.mocked(timetableApi.get).mockResolvedValue({ ...base, status: "UNDER_REVIEW" }); renderWithProviders(<TimetableDetailPage />); const user = userEvent.setup(); await user.click(await screen.findByRole("button", { name: "Return to draft" }));
    await waitFor(() => expect(timetableApi.transition).toHaveBeenCalledWith("tt-1", "return-to-draft", { reason: "Needs correction" }));
  });

  it("hides workflow mutations from read-only roles", async () => {
    roleNames = ["Student"]; vi.mocked(timetableApi.get).mockResolvedValue(base); renderWithProviders(<TimetableDetailPage />); await screen.findByText("College timetable"); expect(screen.queryByRole("button", { name: "Submit for review" })).not.toBeInTheDocument();
  });
});
