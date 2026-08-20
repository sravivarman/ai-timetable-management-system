import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SchedulingSlotsPage from "@/app/(protected)/scheduling-slots/page";
import { listAcademicTerms, masterApi, schedulingSlotApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

let mayManage = true;
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: () => mayManage }) }));
vi.mock("@/lib/api", () => ({
  listAcademicTerms: vi.fn(),
  masterApi: { workingDays: vi.fn() },
  schedulingSlotApi: {
    list: vi.fn(), dates: vi.fn(), matrix: vi.fn(), create: vi.fn(), setDates: vi.fn(),
    bulk: vi.fn(), semesterBulk: vi.fn(), update: vi.fn(), deactivate: vi.fn(), restore: vi.fn(), copy: vi.fn(),
  },
}));

const termId = "00000000-0000-0000-0000-000000000001";
const offeringId = "00000000-0000-0000-0000-000000000010";
const sectionId = "00000000-0000-0000-0000-000000000011";
const slotIds = [1, 2, 3].map((value) => `00000000-0000-0000-0000-00000000002${value}`);
const page = { total: 0, page: 1, page_size: 100, pages: 0 };
const slots = slotIds.map((id, index) => ({
  id, academic_term_id: termId, slot_code: `S0${index + 1}`, slot_name: `Slot ${index + 1}`,
  sequence_number: index + 1, start_date: "2026-08-03", end_date: "2026-08-09",
  working_date_count: index + 4, is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
}));

describe("Scheduling Slot management", () => {
  beforeEach(() => {
    mayManage = true;
    vi.clearAllMocks();
    vi.mocked(listAcademicTerms).mockResolvedValue({ ...page, total: 1, pages: 1, items: [{ id: termId, academic_year: "2026-27", term_name: "I-I", year_number: 1, semester_number: 1, is_active: true, is_current: true }] });
    vi.mocked(masterApi.workingDays).mockResolvedValue({ ...page, total: 2, pages: 1, items: [
      { id: "day-1", day_name: "Monday", sequence_number: 1, is_working_day: true, is_active: true },
      { id: "day-2", day_name: "Tuesday", sequence_number: 2, is_working_day: true, is_active: true },
    ] });
    vi.mocked(schedulingSlotApi.list).mockResolvedValue({ ...page, total: slots.length, pages: 1, items: slots });
    vi.mocked(schedulingSlotApi.dates).mockResolvedValue([{ id: "date-1", scheduling_slot_id: slotIds[0], working_date: "2026-08-03", day_name: "Monday", is_active: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]);
    vi.mocked(schedulingSlotApi.matrix).mockResolvedValue({ slots, rows: [{
      course_offering_id: offeringId, section_id: sectionId, course_code: "A9001", course_name: "Mathematics", course_type: "THEORY", section_code: "CSE-A", section_name: "A", semester_required: 8, allocated_to_slots: 4, remaining_to_allocate: 4, over_allocated: 0, reconciliation_status: "UNDER_ALLOCATED",
      cells: [
        { scheduling_slot_id: slotIds[0], requirement_id: null, sessions_required: null, status: "MISSING" },
        { scheduling_slot_id: slotIds[1], requirement_id: "requirement-2", sessions_required: 0, status: "CONFIGURED_ZERO" },
        { scheduling_slot_id: slotIds[2], requirement_id: "requirement-3", sessions_required: 4, status: "CONFIGURED" },
      ],
    }], completeness: slots.map((slot, index) => ({ scheduling_slot_id: slot.id, slot_code: slot.slot_code, total_active_offerings: 1, configured_positive: index === 2 ? 1 : 0, configured_zero: index === 1 ? 1 : 0, missing: index === 0 ? 1 : 0, invalid: 0, is_complete: index > 0 })) });
    vi.mocked(schedulingSlotApi.setDates).mockResolvedValue([]);
    vi.mocked(schedulingSlotApi.bulk).mockResolvedValue({ inserted: 0, updated: 1, cleared: 0 });
    vi.mocked(schedulingSlotApi.semesterBulk).mockResolvedValue({ inserted: 0, updated: 1, cleared: 0 });
    vi.mocked(schedulingSlotApi.update).mockResolvedValue(slots[0]);
    vi.mocked(schedulingSlotApi.deactivate).mockResolvedValue(undefined);
    vi.mocked(schedulingSlotApi.restore).mockResolvedValue(slots[0]);
    vi.mocked(schedulingSlotApi.copy).mockResolvedValue({ inserted: 1, updated: 0, cleared: 0 });
  });

  it("renders an arbitrary Slot count in sequence order with readable labels", async () => {
    renderWithProviders(<SchedulingSlotsPage />);
    expect(await screen.findByText("Slot 1")).toBeInTheDocument();
    expect(screen.getByText("Slot 2")).toBeInTheDocument();
    expect(screen.getByText("Slot 3")).toBeInTheDocument();
    expect(screen.getAllByText("CSE-A • A9001")).toHaveLength(2);
    expect(screen.queryByText(offeringId)).not.toBeInTheDocument();
  });

  it("keeps missing, explicit zero, and positive requirements distinct", async () => {
    renderWithProviders(<SchedulingSlotsPage />);
    expect(await screen.findByLabelText("Sessions for A9001 / CSE-A in S01")).toHaveValue(null);
    expect(screen.getByLabelText("Sessions for A9001 / CSE-A in S02")).toHaveValue(0);
    expect(screen.getByLabelText("Sessions for A9001 / CSE-A in S03")).toHaveValue(4);
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("Zero allocated")).toBeInTheDocument();
  });

  it("generates actual working dates from institutional days and explicit exclusions", async () => {
    renderWithProviders(<SchedulingSlotsPage />); const user = userEvent.setup();
    await screen.findByText("2026-08-03 • Monday");
    await user.type(screen.getByLabelText("Holiday / excluded dates"), "2026-08-04");
    await user.click(screen.getByRole("button", { name: "Generate Working Dates" }));
    await waitFor(() => expect(vi.mocked(schedulingSlotApi.setDates).mock.calls[0]?.[0]).toBe(slotIds[0]));
    expect(vi.mocked(schedulingSlotApi.setDates).mock.calls[0]?.[1]).toEqual(["2026-08-03"]);
    expect(vi.mocked(schedulingSlotApi.setDates).mock.calls[0]?.[2]).toBe(true);
  });

  it("keeps read-only users out of Slot mutations", async () => {
    mayManage = false;
    renderWithProviders(<SchedulingSlotsPage />);
    await screen.findByText("Slot 1");
    expect(screen.queryByRole("button", { name: "Create Slot" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate Working Dates" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Sessions for A9001 / CSE-A in S01")).toBeDisabled();
  });

  it("updates and deactivates an existing Slot through explicit controls", async () => {
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithProviders(<SchedulingSlotsPage />); const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "Edit" }))[0]);
    const name = screen.getByLabelText("Slot name");
    await user.clear(name); await user.type(name, "Updated Slot");
    await user.click(screen.getByRole("button", { name: "Save Slot" }));
    await waitFor(() => expect(schedulingSlotApi.update).toHaveBeenCalled());
    expect(vi.mocked(schedulingSlotApi.update).mock.calls[0]?.[0]).toBe(slotIds[0]);
    expect(vi.mocked(schedulingSlotApi.update).mock.calls[0]?.[1]).toMatchObject({ slot_name: "Updated Slot" });
    await user.click(screen.getAllByRole("button", { name: "Deactivate" })[0]);
    await waitFor(() => expect(schedulingSlotApi.deactivate).toHaveBeenCalledWith(slotIds[0]));
    confirmation.mockRestore();
  });

  it("copies requirements without silently overwriting the target", async () => {
    renderWithProviders(<SchedulingSlotsPage />); const user = userEvent.setup();
    await user.selectOptions(await screen.findByLabelText("Source Slot"), slotIds[0]);
    await user.selectOptions(screen.getByLabelText("Target Slot"), slotIds[1]);
    await user.click(screen.getByRole("button", { name: "Copy without overwrite" }));
    await waitFor(() => expect(schedulingSlotApi.copy).toHaveBeenCalledWith(slotIds[0], slotIds[1], false));
  });

  it("saves an explicit semester requirement", async () => {
    renderWithProviders(<SchedulingSlotsPage />); const user = userEvent.setup();
    const input = await screen.findByLabelText("Semester sessions for A9001 / CSE-A");
    await user.clear(input); await user.type(input, "12");
    await user.click(screen.getByRole("button", { name: "Save 1 semester change(s)" }));
    await waitFor(() => expect(schedulingSlotApi.semesterBulk).toHaveBeenCalledWith([{ academic_term_id: termId, course_offering_id: offeringId, total_sessions_required: 12 }]));
  });

  it("warns immediately when edited Slot totals exceed the semester requirement", async () => {
    renderWithProviders(<SchedulingSlotsPage />); const user = userEvent.setup();
    const input = await screen.findByLabelText("Sessions for A9001 / CSE-A in S01");
    await user.type(input, "10");
    expect(await screen.findByRole("alert")).toHaveTextContent("exceeds semester requirement by 6 sessions");
  });
});
