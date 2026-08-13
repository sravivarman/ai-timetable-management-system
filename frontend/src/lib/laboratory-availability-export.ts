import { compactAvailabilityPeriods } from "@/lib/laboratory-availability-csv";
import type { MasterRecord } from "@/lib/master-data-api";

export function laboratoryAvailabilityExportRows(
  laboratories: MasterRecord[], departments: MasterRecord[], terms: MasterRecord[], days: MasterRecord[], slots: MasterRecord[],
): Record<string, unknown>[] {
  const departmentCodes = new Map(departments.map((row) => [row.id, row.department_code]));
  const termCodes = new Map(terms.map((row) => [row.id, `${row.academic_year} | ${row.term_name}`]));
  return laboratories.flatMap((laboratory) => {
    const laboratorySlots = slots.filter((slot) => slot.laboratory_id === laboratory.id && slot.is_active !== false);
    const termIds = [...new Set(laboratorySlots.map((slot) => String(slot.academic_term_id)))];
    const currentTermId = String(terms.find((term) => term.is_current === true)?.id ?? "");
    const exportTermId = termIds.includes(currentTermId) ? currentTermId : termIds[0];
    const groups = exportTermId ? [laboratorySlots.filter((slot) => slot.academic_term_id === exportTermId)] : [[]];
    return groups.map((group) => ({
      laboratory_code: laboratory.laboratory_code,
      laboratory_name: laboratory.laboratory_name,
      room_number: laboratory.room_number,
      department_code: departmentCodes.get(String(laboratory.owning_department_id)) ?? "",
      capacity: laboratory.capacity ?? "",
      concurrent_usage_mode: laboratory.concurrent_usage_mode ?? "EXCLUSIVE",
      is_shareable_across_departments: laboratory.is_shareable_across_departments ?? true,
      availability_mode: laboratory.availability_mode ?? (laboratory.is_available_all_periods === false ? "EXCEPT_BLOCKED" : "ALL_PERIODS"),
      academic_term_code: group.length ? termCodes.get(String(group[0].academic_term_id)) ?? "" : "",
      blocked_periods: compactAvailabilityPeriods(group, days, "BLOCKED"),
      allowed_periods: compactAvailabilityPeriods(group, days, "ALLOWED"),
      is_active: laboratory.is_active,
    }));
  });
}
