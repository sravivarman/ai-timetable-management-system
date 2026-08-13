import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RotationMatrixManager } from "@/components/rotation-matrix-manager";
import { masterDataApi } from "@/lib/master-data-api";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/master-data-api", async () => { const actual = await vi.importActual<typeof import("@/lib/master-data-api")>("@/lib/master-data-api"); return { ...actual, masterDataApi: { ...actual.masterDataApi, lookup: vi.fn(), rotationMatrix: vi.fn(), generateRotation: vi.fn(), updateRotationAssignment: vi.fn() } }; });

const data: Record<string, Record<string, unknown>[]> = {
  "/sections": [{ id: "section-1", section_code: "CSE-A", section_name: "A", academic_term_id: "term-1", display_label: "2026-27 I-I • CSE-A" }],
  "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }],
  "/course-offerings": [{ id: "offering-1", course_id: "course-1", section_id: "section-1", academic_term_id: "term-1", laboratory_selection_mode: "RESTRICTED", allowed_laboratory_ids: ["lab-1"], display_label: "CSL1 - Programming Lab (CSE-A)" }, { id: "offering-2", course_id: "course-2", section_id: "section-1", academic_term_id: "term-1", laboratory_selection_mode: "AUTO", display_label: "CSL2 - Graphics Lab (CSE-A)" }],
  "/courses": [{ id: "course-1", eligible_laboratory_ids: ["lab-1", "lab-2"] }, { id: "course-2", eligible_laboratory_ids: ["lab-2"] }],
  "/laboratory-batch-configurations": [{ id: "config-1", course_offering_id: "offering-1", number_of_groups: 2 }, { id: "config-2", course_offering_id: "offering-2", number_of_groups: 2 }],
  "/student-batches": [{ id: "batch-1", section_id: "section-1", batch_name: "A1" }, { id: "batch-2", section_id: "section-1", batch_name: "A2" }],
  "/laboratories": [{ id: "lab-1", laboratory_code: "CSE-P1", laboratory_name: "Programming Laboratory" }, { id: "lab-2", laboratory_code: "CSE-G1", laboratory_name: "Graphics Laboratory" }],
  "/faculty": [{ id: "faculty-1", faculty_code: "VCE001", full_name: "Faculty One" }, { id: "faculty-2", faculty_code: "VCE002", full_name: "Faculty Two" }],
};
const assignment = (id: string, block: string, batch: string, offering: string, lab: string, faculty: string, position: number) => ({ id, rotation_group_id: "rotation-1", rotation_block_id: block, batch_id: batch, course_offering_id: offering, laboratory_id: lab, main_faculty_id: faculty, supporting_faculty_ids: [], session_duration: 2, rotation_position: position, is_active: true });
const matrix = { group: { id: "rotation-1", rotation_code: "CSE-A-ROT", section_id: "section-1", academic_term_id: "term-1" }, student_group_ids: ["batch-1", "batch-2"], course_offering_ids: ["offering-1", "offering-2"], blocks: [{ id: "block-1", rotation_group_id: "rotation-1", block_number: 1, block_name: "Block 1", assignments: [assignment("a1", "block-1", "batch-1", "offering-1", "lab-1", "faculty-1", 1), assignment("a2", "block-1", "batch-2", "offering-2", "lab-2", "faculty-2", 2)] }] };

describe("RotationMatrixManager", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(masterDataApi.lookup).mockImplementation(async (endpoint) => data[endpoint] as never); vi.mocked(masterDataApi.rotationMatrix).mockResolvedValue(matrix as never); vi.mocked(masterDataApi.generateRotation).mockResolvedValue(matrix as never); });
  it("renders the synchronized matrix with readable labels and conflict preview", async () => {
    renderWithProviders(<RotationMatrixManager rotations={[{ id: "rotation-1", rotation_code: "CSE-A-ROT", section_id: "section-1", academic_term_id: "term-1", rotation_type: "CYCLIC" }]} canManage />);
    expect(await screen.findByText("CSL1 - Programming Lab (CSE-A)")).toBeInTheDocument();
    expect(screen.getByText("A1")).toBeInTheDocument(); expect(screen.getByText("A2")).toBeInTheDocument();
    expect(screen.getByText("Programming Laboratory - CSE-P1")).toBeInTheDocument();
    expect(screen.getByText(/No duplicate group, room, faculty, or duration conflicts/)).toBeInTheDocument();
  });
  it("auto-generates a readable two-laboratory rotation", async () => {
    const user = userEvent.setup(); renderWithProviders(<RotationMatrixManager rotations={[]} canManage />);
    await user.click(screen.getByRole("button", { name: /Generate rotation/ }));
    await user.click(screen.getByRole("combobox", { name: "Section" })); await user.click(within(await screen.findByRole("listbox", { name: "Section options" })).getByRole("option", { name: "2026-27 I-I • CSE-A" }));
    await user.click(screen.getByRole("combobox", { name: "Academic term" })); await user.click(within(await screen.findByRole("listbox", { name: "Academic term options" })).getByRole("option", { name: /2026-27/ }));
    await user.type(screen.getByPlaceholderText("CSE-A-LABS"), "cse-rotation");
    await user.click(screen.getByRole("checkbox", { name: /CSL1/ })); await user.click(screen.getByRole("checkbox", { name: /CSL2/ }));
    await user.click(screen.getByRole("button", { name: "Generate matrix" }));
    expect(masterDataApi.generateRotation).toHaveBeenCalledWith(expect.objectContaining({ section_id: "section-1", academic_term_id: "term-1", rotation_code: "CSE-ROTATION", course_offering_ids: ["offering-1", "offering-2"] }));
  });
  it("limits rotation assignment editing to the offering restricted subset", async () => {
    const user = userEvent.setup(); renderWithProviders(<RotationMatrixManager rotations={[{ id: "rotation-1", rotation_code: "CSE-A-ROT", section_id: "section-1", academic_term_id: "term-1", rotation_type: "CYCLIC" }]} canManage />);
    await user.click(await screen.findByRole("button", { name: /CSL1 - Programming Lab/ }));
    await user.click(screen.getByRole("combobox", { name: "Laboratory room" }));
    const listbox = await screen.findByRole("listbox", { name: "Laboratory room options" });
    expect(within(listbox).getByRole("option", { name: /CSE-P1/ })).toBeInTheDocument();
    expect(within(listbox).queryByRole("option", { name: /CSE-G1/ })).not.toBeInTheDocument();
  });
});
