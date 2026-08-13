export type SectionLabelData = object;
export type AcademicTermLabelData = object;

/**
 * Formats a Section consistently without repeating a section letter that is
 * already part of section_code. Academic-term context is included whenever it
 * is available to the caller.
 */
export function sectionLabel(section: SectionLabelData, academicTerm?: AcademicTermLabelData): string {
  const code = clean(field(section, "section_code")) || clean(field(section, "section_name")) || "Section metadata unavailable";
  const term = academicTermLabel(academicTerm);
  return term ? `${term} • ${code}` : code;
}

export function academicTermLabel(term?: AcademicTermLabelData): string {
  if (!term) return "";
  const year = clean(field(term, "academic_year"));
  const name = clean(field(term, "term_name")) || yearSemesterLabel(field(term, "year_number"), field(term, "semester_number"));
  return [year, name].filter(Boolean).join(" ");
}

export function sectionTerm(
  section: SectionLabelData,
  terms: AcademicTermLabelData[] | undefined,
): AcademicTermLabelData | undefined {
  const termId = clean(field(section, "academic_term_id"));
  return terms?.find((term) => clean(field(term, "id")) === termId);
}

function yearSemesterLabel(yearNumber: unknown, semesterNumber: unknown): string {
  const year = Number(yearNumber);
  const semester = Number(semesterNumber);
  if (!Number.isInteger(year) || year < 1 || !Number.isInteger(semester) || semester < 1) return "";
  return `${roman(year)} Year ${roman(semester)} Semester`;
}

function roman(value: number): string {
  return ["", "I", "II", "III", "IV"][value] ?? String(value);
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : value == null ? "" : String(value);
}

function field(value: object, name: string): unknown {
  return (value as Record<string, unknown>)[name];
}
