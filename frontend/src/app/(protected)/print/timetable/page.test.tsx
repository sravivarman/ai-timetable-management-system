import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PrintTimetablePage from "@/app/(protected)/print/timetable/page";
import { timetableApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("version_id=version-1&view_type=faculty&resource_id=faculty-1") }));
vi.mock("@/lib/api", () => ({ timetableApi: { viewGrid: vi.fn() } }));
describe("print timetable", () => {
  it("loads the requested resource view and exposes print controls", async () => { vi.mocked(timetableApi.viewGrid).mockResolvedValue({ version_id: "version-1", view_type: "faculty", resource_id: "faculty-1", schedule_type: "HIGHER_YEAR", days: [{ working_day_id: "day", day_name: "Monday", sequence_number: 1, entries: [{ entry_id: "entry", working_day_id: "day", day_name: "Monday", period_number: 1, period_numbers: [1,2], schedule_type: "HIGHER_YEAR", start_time: "09:10", end_time: "11:00", course_code: "CS101", course_name: "Programming Lab", course_type: "LABORATORY", section_code: "CSE-A", session_length: 2, entry_status: "LOCKED", is_manual: true, is_locked: true }] }] }); renderWithProviders(<PrintTimetablePage />); expect(await screen.findByRole("heading", { name: "Faculty timetable" })).toBeInTheDocument(); expect(screen.getByText("Programming Lab")).toBeInTheDocument(); expect(screen.getByRole("button", { name: /Print/i })).toBeInTheDocument(); expect(timetableApi.viewGrid).toHaveBeenCalledWith("version-1", "faculty", "faculty-1"); });
});
