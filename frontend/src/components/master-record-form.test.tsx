import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MasterRecordForm } from "@/components/master-record-form";
import { masterConfigs } from "@/lib/master-data-config";
import { renderWithProviders } from "@/test/render";

describe("master record form", () => {
  it("validates required fields and submits a create payload", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    renderWithProviders(<MasterRecordForm config={masterConfigs.departments} lookupRecords={{}} mode="create" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Department code is required.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Department code/), "CSE");
    await user.type(screen.getByLabelText(/^Department name/), "Computer Science and Engineering");
    await user.type(screen.getByLabelText(/^Short name/), "CSE");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ department_code: "CSE", short_name: "CSE" }));
  });

  it("separates practical grouping, session pattern, and venue requirements", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MasterRecordForm config={masterConfigs.courses} lookupRecords={{ "/departments": [{ id: "d1", department_code: "CSE", department_name: "Computer Science" }], "/laboratories": [] }} mode="create" busy={false} onClose={vi.fn()} onSubmit={vi.fn()} />);
    await user.selectOptions(screen.getByLabelText("Course type *"), "PRACTICAL");
    expect(screen.queryByLabelText(/Preferred\/default laboratory/)).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: /Grouping/ }), "GROUPED");
    expect(screen.getByLabelText(/^Default number of student groups/)).toBeInTheDocument();
    expect(screen.getByText(/academic periods each student or student group receives/)).toBeInTheDocument();
    expect(screen.getByText(/consecutive timetable periods in one attendance session/)).toBeInTheDocument();
    expect(screen.getByText(/sessions each student or student group attends/)).toBeInTheDocument();
    expect(screen.getByText(/physical scheduling multiplicity, not weekly periods/)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: /Venue requirement/ }), "CLASSROOM_OR_LABORATORY");
    expect(screen.getByRole("combobox", { name: "Preferred Laboratory" })).toBeInTheDocument();
    expect(screen.getByText(/Practical courses do not necessarily require a laboratory/)).toBeInTheDocument();
  });

  it("shows searchable eligible laboratories and limits the preferred selector", async () => {
    const user = userEvent.setup();
    const laboratories = [
      { id: "lab-1", laboratory_code: "GRAPHICS-LAB-1", laboratory_name: "Graphics Lab 1" },
      { id: "lab-2", laboratory_code: "GRAPHICS-LAB-2", laboratory_name: "Graphics Lab 2" },
      { id: "chem", laboratory_code: "CHEM-LAB", laboratory_name: "Chemistry Lab" },
    ];
    renderWithProviders(<MasterRecordForm config={masterConfigs.courses} initial={{ id: "course-1", course_code: "A9301", course_name: "Engineering Graphics", offering_department_id: "d1", course_type: "PRACTICAL", weekly_periods: 3, grouping_mode: "FULL_SECTION", session_duration: 3, sessions_per_week: 1, venue_requirement: "CLASSROOM_OR_LABORATORY", eligible_laboratory_ids: ["lab-1", "lab-2"], default_laboratory_id: "lab-1" }} lookupRecords={{ "/departments": [{ id: "d1", department_code: "MEC", department_name: "Mechanical" }], "/laboratories": laboratories }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Eligible Laboratories")).toBeInTheDocument();
    expect(screen.getByText(/GRAPHICS-LAB-1/)).toBeInTheDocument();
    expect(screen.getByText(/GRAPHICS-LAB-2/)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Preferred Laboratory" })).toBeInTheDocument();
    expect(screen.queryByText("lab-1")).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Search Eligible Laboratories" }), "Chemistry");
    expect(screen.getByText(/CHEM-LAB/)).toBeInTheDocument();
    expect(screen.queryByText(/GRAPHICS-LAB-2/)).not.toBeInTheDocument();
  });

  it("supports AUTO, PREFERRED, and FIXED offering laboratory assignment", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={{ id: "off-1", course_id: "course-1", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true, laboratory_selection_mode: "AUTO" }} lookupRecords={{ "/courses": [{ id: "course-1", course_code: "A9301", course_name: "Engineering Graphics", venue_requirement: "LABORATORY_ONLY", eligible_laboratory_ids: ["lab-1", "lab-2"] }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • MEC-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }], "/laboratories": [{ id: "lab-1", laboratory_code: "GRAPHICS-LAB-1", laboratory_name: "Graphics Lab 1" }, { id: "lab-2", laboratory_code: "GRAPHICS-LAB-2", laboratory_name: "Graphics Lab 2" }, { id: "chem", laboratory_code: "CHEM-LAB", laboratory_name: "Chemistry Lab" }] }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.getByRole("radio", { name: /Automatic selection/ })).toBeChecked();
    expect(screen.queryByLabelText("Required Laboratory *")).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Require a laboratory/ }));
    expect(screen.getByRole("combobox", { name: "Required Laboratory *" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Required laboratory is required.")).toBeInTheDocument();
  });

  it("selects multiple course-eligible laboratories for RESTRICTED and rejects an empty set", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={{ id: "off-1", course_id: "course-1", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true, laboratory_selection_mode: "AUTO" }} lookupRecords={{ "/courses": [{ id: "course-1", course_code: "A9008", course_name: "Engineering Physics Laboratory", venue_requirement: "LABORATORY_ONLY", eligible_laboratory_ids: ["lab-3117", "lab-5014"] }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • ECE-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }], "/laboratories": [{ id: "lab-1117", laboratory_code: "1117", laboratory_name: "Physics Lab" }, { id: "lab-3117", laboratory_code: "3117", laboratory_name: "Physics Lab" }, { id: "lab-5014", laboratory_code: "5014", laboratory_name: "Physics Lab" }] }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    await user.click(screen.getByRole("radio", { name: /Restrict to selected laboratories/ }));
    expect(screen.getByText("3117 · Physics Lab")).toBeInTheDocument();
    expect(screen.getByText("5014 · Physics Lab")).toBeInTheDocument();
    expect(screen.queryByText("1117 · Physics Lab")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Select at least one allowed laboratory.")).toBeInTheDocument();
    await user.click(screen.getByLabelText("3117 · Physics Lab"));
    await user.click(screen.getByLabelText("5014 · Physics Lab"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ laboratory_selection_mode: "RESTRICTED", laboratory_override_id: null, allowed_laboratory_ids: ["lab-3117", "lab-5014"] }));
  });

  it("hides and clears laboratory assignment when the course changes to classroom-only", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    const initial = { id: "off-lab", course_id: "lab-course", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true, laboratory_selection_mode: "FIXED", laboratory_override_id: "lab-2" };
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={initial} lookupRecords={{ "/courses": [{ id: "lab-course", course_code: "CSL1", course_name: "Programming Laboratory", venue_requirement: "LABORATORY_ONLY", eligible_laboratory_ids: ["lab-1", "lab-2"] }, { id: "theory-course", course_code: "A9001", course_name: "Matrices and Calculus", venue_requirement: "CLASSROOM_ONLY" }, { id: "flex-course", course_code: "CCDT", course_name: "Design Thinking", venue_requirement: "CLASSROOM_OR_LABORATORY", eligible_laboratory_ids: ["lab-1"] }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • CIV-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }], "/laboratories": [{ id: "lab-1", laboratory_code: "LAB-1", laboratory_name: "Lab One" }, { id: "lab-2", laboratory_code: "LAB-2", laboratory_name: "Lab Two" }] }} mode="create" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.getByRole("radio", { name: /Require a laboratory/ })).toBeChecked();
    await user.click(screen.getByRole("combobox", { name: "Course *" }));
    await user.click(screen.getByRole("option", { name: /A9001.*Matrices and Calculus/ }));
    expect(screen.queryByText("Automatic selection")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /Laboratory/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ course_id: "theory-course", laboratory_selection_mode: "AUTO", laboratory_override_id: null }));
    await user.click(screen.getByRole("combobox", { name: "Course *" }));
    await user.click(screen.getByRole("option", { name: /CCDT.*Design Thinking/ }));
    expect(screen.getByText("Automatic selection")).toBeInTheDocument();
  });

  it("hides laboratory controls when editing an existing classroom-only offering", async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={{ id: "off-theory", course_id: "theory-course", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true, laboratory_selection_mode: "AUTO", laboratory_override_id: null }} lookupRecords={{ "/courses": [{ id: "theory-course", course_code: "A9001", course_name: "Matrices and Calculus", venue_requirement: "CLASSROOM_ONLY" }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • CIV-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }], "/laboratories": [] }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.queryByText("Automatic selection")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /Laboratory/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ laboratory_selection_mode: "AUTO", laboratory_override_id: null }));
  });

  it("warns before discarding a dirty form", async () => {
    const user = userEvent.setup(); const close = vi.fn(); vi.spyOn(window, "confirm").mockReturnValue(false);
    renderWithProviders(<MasterRecordForm config={masterConfigs.departments} lookupRecords={{}} mode="create" busy={false} onClose={close} onSubmit={vi.fn()} />);
    await user.type(screen.getByLabelText("Department code *"), "CSE");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(window.confirm).toHaveBeenCalledWith("Discard unsaved changes?");
    expect(close).not.toHaveBeenCalled();
  });

  it("uses explicit laboratory availability modes instead of an ambiguous checkbox", () => {
    renderWithProviders(<MasterRecordForm config={masterConfigs.laboratories} lookupRecords={{ "/departments": [] }} mode="create" busy={false} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "Available all instructional periods" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Available except blocked periods" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Available only during selected periods" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /available all periods/i })).not.toBeInTheDocument();
  });

  it("defaults laboratory concurrency to Exclusive and requires capacity for Capacity Shared", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    renderWithProviders(<MasterRecordForm config={masterConfigs.laboratories} initial={{ id: "new-laboratory", laboratory_code: "WS-5A01", laboratory_name: "Engineering Workshop", room_number: "5A01", owning_department_id: "department-1" }} lookupRecords={{ "/departments": [{ id: "department-1", department_code: "MEC", department_name: "Mechanical Engineering" }] }} mode="create" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.getByRole("combobox", { name: /^Concurrent Usage Mode/ })).toHaveValue("EXCLUSIVE");
    expect(screen.queryByLabelText(/^Capacity/)).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: /^Concurrent Usage Mode/ }), "CAPACITY_SHARED");
    expect(screen.getByText(/combined student strength does not exceed capacity/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText(/Capacity is required and must be greater than zero/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Capacity/), "60");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ concurrent_usage_mode: "CAPACITY_SHARED", capacity: 60 }));
  });

  it("creates an ordinary course offering without legacy common-theory controls", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    const initial = { id: "new-offering", course_id: "course-1", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true };
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={initial} lookupRecords={{ "/courses": [{ id: "course-1", course_code: "A9001", course_name: "Matrices and Calculus" }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • MEC-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }] }} mode="create" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.queryByText(/^Common theory$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Common theory group/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ course_id: "course-1", section_id: "section-1", academic_term_id: "term-1", is_mandatory: true }));
    expect(submit.mock.calls[0][0]).not.toHaveProperty("is_common_theory");
    expect(submit.mock.calls[0][0]).not.toHaveProperty("common_theory_group_code");
  });

  it("does not expose or resubmit legacy common-theory values while editing", async () => {
    const user = userEvent.setup(); const submit = vi.fn();
    const initial = {
      id: "offering-1",
      course_id: "course-1",
      section_id: "section-1",
      academic_term_id: "term-1",
      is_mandatory: true,
      is_common_theory: true,
      common_theory_group_code: "LEGACY-GROUP",
    };
    renderWithProviders(<MasterRecordForm config={masterConfigs["course-offerings"]} initial={initial} lookupRecords={{ "/courses": [{ id: "course-1", course_code: "A9001", course_name: "Matrices and Calculus" }], "/sections": [{ id: "section-1", display_label: "2026-27 I-I • MEC-A" }], "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }] }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={submit} />);
    expect(screen.queryByText(/^Common theory$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Common theory group/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit.mock.calls[0][0]).not.toHaveProperty("is_common_theory");
    expect(submit.mock.calls[0][0]).not.toHaveProperty("common_theory_group_code");
  });

  it("configures a combined class with readable offerings and a live capacity summary", () => {
    const initial = { id: "group-1", academic_term_id: "term-1", group_code: "DS-CSE-AB", group_name: "Data Structures A+B", course_id: "course-1", faculty_id: "faculty-1", course_offering_ids: ["offering-a", "offering-b"], preferred_classroom_id: "room-1101", is_active: true };
    const lookupRecords = {
      "/academic-terms": [{ id: "term-1", academic_year: "2026-27", term_name: "I-I" }],
      "/courses": [{ id: "course-1", course_code: "CS301", course_name: "Data Structures" }],
      "/faculty": [{ id: "faculty-1", faculty_code: "VCE042", full_name: "Dr. X" }],
      "/course-offerings": [
        { id: "offering-a", display_label: "CS301 - Data Structures (2026-27 I-I • CSE-A)", section_strength: 72 },
        { id: "offering-b", display_label: "CS301 - Data Structures (2026-27 I-I • CSE-B)", section_strength: 72 },
        { id: "offering-c", display_label: "CS301 - Data Structures (2026-27 I-I • CSE-C)", section_strength: 72 },
      ],
      "/classrooms": [{ id: "room-1101", display_label: "Room 1101 • Capacity 150", room_number: "1101", capacity: 150 }],
      "/laboratories": [],
    };
    renderWithProviders(<MasterRecordForm config={masterConfigs["combined-teaching-groups"]} initial={initial} lookupRecords={lookupRecords} mode="edit" busy={false} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getAllByText(/2026-27 I-I • CSE-A/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2026-27 I-I • CSE-B/).length).toBeGreaterThan(0);
    expect(screen.getByText("Combined strength: 144")).toBeInTheDocument();
    expect(screen.getByText("Room capacity: 150")).toBeInTheDocument();
    expect(screen.getByText("Capacity OK")).toBeInTheDocument();
    expect(screen.queryByText(/offering-a/)).not.toBeInTheDocument();
  });

  it("shows a combined-class capacity warning", () => {
    const initial = { id: "group-1", academic_term_id: "term-1", group_code: "DS-CSE-AB", group_name: "Data Structures A+B", course_id: "course-1", faculty_id: "faculty-1", course_offering_ids: ["offering-a", "offering-b"], preferred_classroom_id: "room-1205" };
    renderWithProviders(<MasterRecordForm config={masterConfigs["combined-teaching-groups"]} initial={initial} lookupRecords={{ "/academic-terms": [], "/courses": [], "/faculty": [], "/course-offerings": [{ id: "offering-a", display_label: "CSE-A - Data Structures", section_strength: 72 }, { id: "offering-b", display_label: "CSE-B - Data Structures", section_strength: 72 }], "/classrooms": [{ id: "room-1205", display_label: "Room 1205 • Capacity 120", capacity: 120 }], "/laboratories": [] }} mode="edit" busy={false} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Capacity exceeded")).toHaveClass("text-red-700");
  });
});
