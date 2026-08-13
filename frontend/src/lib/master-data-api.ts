import { api } from "@/lib/api-client";
import type { MasterConfig } from "@/lib/master-data-config";
import { sectionLabel, sectionTerm } from "@/lib/section-labels";
import type { Page } from "@/lib/types";

export type MasterRecord = Record<string, unknown> & { id: string; is_active?: boolean };
export type RotationAssignment = MasterRecord & { rotation_block_id: string; batch_id: string; course_offering_id: string; laboratory_id?: string | null; main_faculty_id: string; supporting_faculty_ids: string[]; session_duration: number; rotation_position: number };
export type RotationBlock = MasterRecord & { rotation_group_id: string; block_number: number; block_name?: string | null; assignments: RotationAssignment[] };
export type RotationMatrix = { group: MasterRecord; blocks: RotationBlock[]; student_group_ids: string[]; course_offering_ids: string[] };
export type ListParams = { page?: number; page_size?: number; search?: string; is_active?: boolean | string; [key: string]: string | number | boolean | undefined };

function normalizePage(data: unknown, page = 1, pageSize = 20): Page<MasterRecord> {
  if (Array.isArray(data)) return { items: data as MasterRecord[], total: data.length, page, page_size: pageSize, pages: Math.ceil(data.length / pageSize) };
  const value = data as Partial<Page<MasterRecord>> | undefined;
  return { items: value?.items ?? [], total: value?.total ?? value?.items?.length ?? 0, page: value?.page ?? page, page_size: value?.page_size ?? pageSize, pages: value?.pages ?? Math.ceil((value?.total ?? 0) / pageSize) };
}

export const masterDataApi = {
  async list(config: MasterConfig, params: ListParams = {}) {
    const page = Number(params.page ?? 1); const pageSize = Number(params.page_size ?? 20);
    const result = normalizePage((await api.get(config.endpoint, { params })).data, page, pageSize);
    if (config.endpoint === "/combined-teaching-groups") {
      const items: MasterRecord[] = result.items.map((row) => ({ ...row, course_offering_ids: Array.isArray(row.offerings) ? (row.offerings as MasterRecord[]).map((offering) => String(offering.course_offering_id)) : [] }));
      return { ...result, items };
    }
    if (config.endpoint !== "/sections") return result;
    return { ...result, items: await enrichSections(result.items) };
  },
  async get(config: MasterConfig, id: string) { return (await api.get<MasterRecord>(`${config.endpoint}/${id}`)).data; },
  async create(config: MasterConfig, payload: Record<string, unknown>) { return (await api.post<MasterRecord>(config.endpoint, payload)).data; },
  async update(config: MasterConfig, id: string, payload: Record<string, unknown>, expectedUpdatedAt?: string) { return (await api.put<MasterRecord>(`${config.endpoint}/${id}`, payload, importBaselineHeaders(id, expectedUpdatedAt))).data; },
  async remove(config: MasterConfig, id: string, expectedUpdatedAt?: string) { await api.delete(`${config.endpoint}/${id}`, importBaselineHeaders(id, expectedUpdatedAt)); },
  async restore(config: MasterConfig, id: string, expectedUpdatedAt?: string) { return (await api.post<MasterRecord>(`${config.endpoint}/${id}/restore`, undefined, importBaselineHeaders(id, expectedUpdatedAt))).data; },
  async lookup(endpoint: string, includeInactive = false): Promise<MasterRecord[]> {
    const rows = await lookupRows(endpoint, includeInactive);
    if (endpoint === "/classrooms") {
      return rows.map((row) => ({ ...row, display_label: [`Room ${row.room_number}`, row.room_name, row.capacity == null ? "Capacity not configured" : `Capacity ${row.capacity}`].filter(Boolean).join(" • ") }));
    }
    if (endpoint === "/sections") {
      return enrichSections(rows);
    }
    if (endpoint === "/course-offerings") {
      const [courses, sections] = await Promise.all([lookupRows("/courses", includeInactive), lookupRows("/sections", includeInactive)]);
      const courseMap = new Map(courses.map((row) => [row.id, row]));
      const terms = await lookupRows("/academic-terms", true);
      const sectionMap = new Map(sections.map((row) => [row.id, row]));
      return rows.map((row) => { const section = sectionMap.get(String(row.section_id)); const course = courseMap.get(String(row.course_id)); const courseLabel = course ? [course.course_code, course.course_name].filter(Boolean).join(" - ") : "Course metadata unavailable"; return ({ ...row, course_code: course?.course_code, course_name: course?.course_name, course_type: course?.course_type, section_code: section?.section_code, section_strength: section?.student_strength, display_label: `${courseLabel} (${section ? sectionLabel(section, sectionTerm(section, terms)) : "Section metadata unavailable"})` }); });
    }
    if (endpoint === "/laboratory-batch-configurations") {
      const offerings: MasterRecord[] = await masterDataApi.lookup("/course-offerings", includeInactive);
      const offeringMap = new Map(offerings.map((row) => [row.id, String(row.display_label)]));
      return rows.map((row) => ({ ...row, display_label: `${offeringMap.get(String(row.course_offering_id)) ?? "Offering metadata unavailable"} - ${row.number_of_groups ?? "?"} student groups` }));
    }
    return rows;
  },
  async all(config: MasterConfig, params: ListParams = {}) { const first = await this.list(config, { ...params, page: 1, page_size: 100 }); const items = [...first.items]; for (let page = 2; page <= first.pages; page++) items.push(...(await this.list(config, { ...params, page, page_size: 100 })).items); return items; },
  async generateBatches(payload: { section_id: string; number_of_groups: number; naming_pattern: string; overwrite: boolean }) { return (await api.post<MasterRecord[]>("/student-batches/generate", payload)).data; },
  async generateRotation(payload: { section_id: string; academic_term_id: string; rotation_code: string; course_offering_ids: string[]; student_group_ids?: string[]; overwrite?: boolean }) { return (await api.post<RotationMatrix>("/laboratory-rotations/generate", payload)).data; },
  async rotationMatrix(groupId: string) { return (await api.get<RotationMatrix>(`/laboratory-rotations/${groupId}/matrix`)).data; },
  async createRotationBlock(groupId: string, payload: { block_number: number; block_name?: string }) { return (await api.post<RotationBlock>(`/laboratory-rotations/${groupId}/blocks`, payload)).data; },
  async createRotationAssignment(groupId: string, payload: Record<string, unknown>) { return (await api.post<RotationAssignment>(`/laboratory-rotations/${groupId}/assignments`, payload)).data; },
  async updateRotationAssignment(assignmentId: string, payload: Record<string, unknown>) { return (await api.put<RotationAssignment>(`/laboratory-rotations/assignments/${assignmentId}`, payload)).data; },
};

function importBaselineHeaders(id: string, expectedUpdatedAt?: string) {
  return expectedUpdatedAt ? { headers: { "X-Import-Target-Id": id, "X-Import-Expected-Updated-At": expectedUpdatedAt } } : undefined;
}

async function lookupRows(endpoint: string, includeInactive = false): Promise<MasterRecord[]> {
  if (includeInactive && ["/departments", "/programs"].includes(endpoint)) return pagedLookupRows(endpoint, { include_inactive: true });
  const active = await pagedLookupRows(endpoint, { is_active: true });
  if (!includeInactive) return active;
  const inactive = await pagedLookupRows(endpoint, { is_active: false });
  return [...new Map([...active, ...inactive].map((row) => [row.id, row])).values()];
}

async function pagedLookupRows(endpoint: string, filters: Record<string, boolean>): Promise<MasterRecord[]> {
  const first = normalizePage((await api.get(endpoint, { params: { page: 1, page_size: 100, ...filters } })).data, 1, 100);
  const items = [...first.items];
  for (let page = 2; page <= first.pages; page++) items.push(...normalizePage((await api.get(endpoint, { params: { page, page_size: 100, ...filters } })).data, page, 100).items);
  return items;
}

async function enrichSections(rows: MasterRecord[]): Promise<MasterRecord[]> {
  const terms = await lookupRows("/academic-terms", true);
  return rows.map((row) => ({ ...row, display_label: sectionLabel(row, sectionTerm(row, terms)) }));
}
