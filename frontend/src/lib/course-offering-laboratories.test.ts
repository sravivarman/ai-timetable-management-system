import { describe, expect, it } from "vitest";
import { laboratoryAssignmentPresentation } from "@/lib/course-offering-laboratories";

describe("Course Offering laboratory presentation", () => {
  it.each([
    ["THEORY classroom", "CLASSROOM_ONLY", "AUTO", undefined, "—", "—"],
    ["PRACTICAL classroom", "CLASSROOM_ONLY", "AUTO", undefined, "—", "—"],
    ["no fixed venue", "NO_FIXED_VENUE", "AUTO", undefined, "—", "—"],
    ["laboratory automatic", "LABORATORY_ONLY", "AUTO", undefined, "Automatic", "Any eligible laboratory"],
    ["laboratory preferred", "LABORATORY_ONLY", "PREFERRED", "GRAPHICS-1 · Graphics Lab 1", "Preferred", "GRAPHICS-1 · Graphics Lab 1"],
    ["laboratory fixed", "LABORATORY_ONLY", "FIXED", "GRAPHICS-2 · Graphics Lab 2", "Required", "GRAPHICS-2 · Graphics Lab 2"],
  ])("renders %s correctly", (_name, venue, mode, label, assignment, laboratory) => {
    expect(laboratoryAssignmentPresentation({ id: "offering", laboratory_selection_mode: mode }, { id: "course", venue_requirement: venue }, label)).toEqual({ assignment, laboratory });
  });
});
