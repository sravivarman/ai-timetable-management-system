import type { MasterRecord } from "@/lib/master-data-api";

const LABORATORY_CAPABLE_VENUES = new Set(["LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"]);

export function isLaboratoryCapableCourse(course?: MasterRecord): boolean {
  return LABORATORY_CAPABLE_VENUES.has(String(course?.venue_requirement ?? ""));
}

export function laboratoryAssignmentPresentation(
  offering: MasterRecord,
  course: MasterRecord | undefined,
  laboratoryLabel?: string,
  allowedLaboratoryLabels: string[] = [],
): { assignment: string; laboratory: string } {
  if (!isLaboratoryCapableCourse(course)) return { assignment: "—", laboratory: "—" };
  const mode = String(offering.laboratory_selection_mode || "AUTO");
  if (mode === "PREFERRED") return { assignment: "Preferred", laboratory: laboratoryLabel ?? "Laboratory metadata unavailable" };
  if (mode === "FIXED") return { assignment: "Required", laboratory: laboratoryLabel ?? "Laboratory metadata unavailable" };
  if (mode === "RESTRICTED") return { assignment: "Restricted", laboratory: allowedLaboratoryLabels.length ? allowedLaboratoryLabels.join(", ") : "Laboratory metadata unavailable" };
  return { assignment: "Automatic", laboratory: "Any eligible laboratory" };
}

export function normalizeOfferingLaboratoryPayload(payload: Record<string, unknown>, course?: MasterRecord) {
  if (isLaboratoryCapableCourse(course)) {
    const mode = payload.laboratory_selection_mode ?? "AUTO";
    if (mode === "AUTO" || mode === "RESTRICTED") payload.laboratory_override_id = null;
    if (mode !== "RESTRICTED") payload.allowed_laboratory_ids = [];
    return payload;
  }
  payload.laboratory_selection_mode = "AUTO";
  payload.laboratory_override_id = null;
  payload.allowed_laboratory_ids = [];
  return payload;
}
