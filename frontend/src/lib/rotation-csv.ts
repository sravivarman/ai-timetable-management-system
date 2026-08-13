import type { MasterRecord, RotationMatrix } from "@/lib/master-data-api";
import { readableRecordLabel } from "@/lib/readable-labels";

export const rotationAssignmentCsvColumns = ["section_code", "academic_term_code", "rotation_code", "block_number", "student_group_name", "course_code", "laboratory_code", "main_faculty_code", "supporting_faculty_codes", "session_duration"] as const;
export type RotationCsvRow = Record<(typeof rotationAssignmentCsvColumns)[number], string>;
export type ResolvedRotationCsvRow = { source: Record<string, string>; blockNumber?: number; assignmentId?: string; payload?: Record<string, unknown>; resolved: string[]; errors: string[] };

export function resolveRotationCsvRow(source: Record<string, string>, matrix: RotationMatrix, records: Record<string, MasterRecord[]>): ResolvedRotationCsvRow {
  const errors: string[] = []; const resolved: string[] = [];
  const one = (rows: MasterRecord[], predicate: (row: MasterRecord) => boolean, label: string, value: string) => { const matches = rows.filter(predicate); if (matches.length !== 1) { errors.push(matches.length ? `Ambiguous ${label} '${value}'.` : `Unknown ${label} '${value}'.`); return undefined; } if (matches[0].is_active === false) { errors.push(`Referenced ${label} '${value}' is inactive.`); return undefined; } resolved.push(`${label}: ${readableRecordLabel(endpointFor(label), matches[0])}`); return matches[0]; };
  const section = one(records["/sections"] ?? [], (row) => normalize(row.section_code) === normalize(source.section_code), "section", source.section_code);
  const term = one(records["/academic-terms"] ?? [], (row) => termCode(row) === normalizeTerm(source.academic_term_code), "academic term", source.academic_term_code);
  if (normalize(matrix.group.rotation_code) !== normalize(source.rotation_code)) errors.push(`Rotation code '${source.rotation_code}' does not match the selected matrix.`);
  if (section && matrix.group.section_id !== section.id) errors.push("Section does not match the selected rotation group.");
  if (term && matrix.group.academic_term_id !== term.id) errors.push("Academic term does not match the selected rotation group.");
  const blockNumber = Number(source.block_number); if (!Number.isInteger(blockNumber) || blockNumber < 1) errors.push("Rotation block number must be a positive integer.");
  const block = matrix.blocks.find((item) => item.block_number === blockNumber); resolved.push(`block: ${block ? block.block_name || `Block ${block.block_number}` : `New Block ${blockNumber}`}`);
  const batch = one((records["/student-batches"] ?? []).filter((row) => !section || row.section_id === section.id), (row) => normalize(row.batch_name) === normalize(source.student_group_name), "student group", source.student_group_name);
  const course = one(records["/courses"] ?? [], (row) => normalize(row.course_code) === normalize(source.course_code), "course", source.course_code);
  const offering = course && section && term ? one(records["/course-offerings"] ?? [], (row) => row.course_id === course.id && row.section_id === section.id && row.academic_term_id === term.id, "course offering", `${source.course_code} / ${source.section_code} / ${source.academic_term_code}`) : undefined;
  const laboratory = one(records["/laboratories"] ?? [], (row) => normalize(row.laboratory_code) === normalize(source.laboratory_code), "laboratory", source.laboratory_code);
  const main = one(records["/faculty"] ?? [], (row) => normalize(row.faculty_code) === normalize(source.main_faculty_code), "faculty", source.main_faculty_code);
  const supporting = source.supporting_faculty_codes?.split(/[;|]/).map((value) => value.trim()).filter(Boolean).map((code) => one(records["/faculty"] ?? [], (row) => normalize(row.faculty_code) === normalize(code), "faculty", code)).filter(Boolean) as MasterRecord[] ?? [];
  const duration = Number(source.session_duration); if (![2, 3].includes(duration)) errors.push("Session duration must be 2 or 3.");
  if (errors.length || !batch || !offering || !laboratory || !main) return { source, blockNumber, resolved, errors };
  const existing = block?.assignments.find((assignment) => assignment.batch_id === batch.id);
  return { source, blockNumber, assignmentId: existing?.id, resolved, errors, payload: { ...(block ? { rotation_block_id: block.id } : {}), batch_id: batch.id, course_offering_id: offering.id, laboratory_id: laboratory.id, main_faculty_id: main.id, supporting_faculty_ids: supporting.map((row) => row.id), session_duration: duration, rotation_position: Number(batch.sequence_number ?? existing?.rotation_position ?? 1) } };
}

function endpointFor(label: string) { return ({ section: "/sections", "academic term": "/academic-terms", "student group": "/student-batches", course: "/courses", "course offering": "/course-offerings", laboratory: "/laboratories", faculty: "/faculty" } as Record<string, string>)[label] ?? ""; }
function normalize(value: unknown) { return String(value ?? "").trim().toUpperCase(); }
function termCode(row: MasterRecord) { return `${normalize(row.academic_year)}|${normalize(row.term_name)}`; }
function normalizeTerm(value: unknown) { return normalize(value).replace(/\s*(?:\||\/|:)\s*/, "|").replace(/\s+/, "|"); }
