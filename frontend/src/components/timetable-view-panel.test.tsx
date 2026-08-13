import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TimetableViewPanel, type TimetableViewType } from "@/components/timetable-view-panel";
import { timetableApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({ timetableApi: { viewGrid: vi.fn() } }));
const emptyGrid = { version_id: "version", view_type: "faculty", resource_id: "resource", schedule_type: "HIGHER_YEAR", days: [{ working_day_id: "day", day_name: "Monday", sequence_number: 1, entries: [] }] };

describe("Timetable resource views", () => {
  it("shows a readable selector label without exposing its UUID", async () => {
    const resourceId = "d053cef9-62d5-4fdd-b11d-bc1cf4520827";
    renderWithProviders(<TimetableViewPanel versionId="version" viewType="faculty" options={[{ id: resourceId, label: "VCE042 - Dr. R. Kumar" }]} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "Faculty" }));
    expect(screen.getByRole("option", { name: "VCE042 - Dr. R. Kumar" })).toBeInTheDocument();
    expect(screen.queryByText(resourceId)).not.toBeInTheDocument();
  });

  it.each(["section", "faculty", "classroom", "laboratory", "batch"] as TimetableViewType[])("loads the backend %s view", async (viewType) => {
    vi.mocked(timetableApi.viewGrid).mockResolvedValue({ ...emptyGrid, view_type: viewType });
    renderWithProviders(<TimetableViewPanel versionId="version" viewType={viewType} options={[{ id: "resource", label: "Readable resource" }]} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Readable resource" }));
    await user.click(screen.getByRole("button", { name: new RegExp(`Load ${viewType === "batch" ? "student batch" : viewType} view`, "i") }));
    await waitFor(() => expect(timetableApi.viewGrid).toHaveBeenCalledWith("version", viewType, "resource"));
    expect(await screen.findByText(`This ${viewType} has no entries in the selected version.`)).toBeInTheDocument();
  });
});
