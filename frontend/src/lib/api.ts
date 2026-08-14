import { api } from "@/lib/api-client";
import type { AcademicTerm, Classroom, ConflictReport, Course, Department, EntryAudit, Faculty, FreeResourceResponse, Laboratory, Page, Program, QualityMetrics, ReportDefinition, ReportFilterOptions, ReportPreview, ReportRequest, Role, Section, SolverInputSnapshot, SolverRun, StatusHistory, StudentBatch, Timetable, TimetableEntry, TimetableGrid, TimetableVersion, TokenPair, User, ValidationIssue, ValidationRun, VersionComparison, WorkingDay, WorkloadPreview } from "@/lib/types";

export const authApi = {
  async login(username: string, password: string) { const form = new URLSearchParams({ username, password }); return (await api.post<TokenPair>("/auth/login", form, { headers: { "Content-Type": "application/x-www-form-urlencoded" } })).data },
  async me() { return (await api.get<User>("/auth/me")).data },
  async logout() { await api.post("/auth/logout") },
  async changePassword(current_password: string, new_password: string) { await api.post("/auth/change-password", { current_password, new_password }) },
};
export const usersAdminApi = {
  async list() { return (await api.get<User[]>("/users")).data },
  async get(id: string) { return (await api.get<User>(`/users/${id}`)).data },
  async create(payload: { username: string; email: string; full_name: string; password: string; role_ids: string[] }) { return (await api.post<User>("/users", payload)).data },
  async update(id: string, payload: { username?: string; email?: string; full_name?: string; password?: string; is_active?: boolean; role_ids?: string[] }) { return (await api.put<User>(`/users/${id}`, payload)).data },
  async remove(id: string) { await api.delete(`/users/${id}`) },
  async roles() { return (await api.get<Role[]>("/roles")).data },
};
export const timetableApi = {
  async list(params: Record<string, string | number | undefined>) { return (await api.get<Page<Timetable>>("/timetables", { params })).data },
  async get(id: string) { return (await api.get<Timetable>(`/timetables/${id}`)).data },
  async versions(id: string) { return (await api.get<Page<TimetableVersion>>(`/timetables/${id}/versions`, { params: { page_size: 100 } })).data },
  async version(id: string) { return (await api.get<TimetableVersion>(`/timetable-versions/${id}`)).data },
  async history(id: string) { return (await api.get<StatusHistory[]>(`/timetables/${id}/status-history`)).data },
  async entries(id: string, params: Record<string, string | number | boolean | undefined> = {}) { return (await api.get<Page<TimetableEntry>>(`/timetable-versions/${id}/entries`, { params: { page_size: 100, ...params } })).data },
  async solverRuns(id: string) { return (await api.get<Page<SolverRun>>(`/timetable-versions/${id}/solver-runs`, { params: { page_size: 100 } })).data },
  async quality(runId: string) { return (await api.get<QualityMetrics>(`/solver-runs/${runId}/quality`)).data },
  async conflicts(id: string) { return (await api.get<ConflictReport>(`/timetable-versions/${id}/conflicts`)).data },
  async viewGrid(id: string, viewType: "section" | "faculty" | "classroom" | "laboratory" | "batch", resourceId: string) { return (await api.get<TimetableGrid>(`/timetable-versions/${id}/views/${viewType}/${resourceId}`)).data },
  async sectionGrid(id: string, sectionId: string) { return this.viewGrid(id, "section", sectionId) },
  async transition(id: string, action: string, body: Record<string, unknown> = {}) { return (await api.post<Timetable>(`/timetables/${id}/${action}`, body)).data },
};
export const solverApi = {
  async list(params: { timetable_version_id?: string; status?: string; page?: number; page_size?: number } = {}) { return (await api.get<Page<SolverRun>>("/solver-runs", { params })).data },
  async get(id: string) { return (await api.get<SolverRun>(`/solver-runs/${id}`)).data },
  async quality(id: string) { return (await api.get<QualityMetrics>(`/solver-runs/${id}/quality`)).data },
};
export const validationApi = {
  async run(payload: { academic_term_id: string; scope_type: string; department_id?: string; program_id?: string; section_id?: string }) { return (await api.post<ValidationRun>("/timetable-validation/run", payload)).data },
  async list(params: { academic_term_id?: string; scope_type?: string; status?: string; page?: number; page_size?: number }) { return (await api.get<Page<ValidationRun>>("/timetable-validation/runs", { params })).data },
  async get(id: string) { return (await api.get<ValidationRun>(`/timetable-validation/runs/${id}`)).data },
  async issues(id: string, params: { severity?: string; issue_code?: string; page?: number; page_size?: number } = {}) { return (await api.get<Page<ValidationIssue>>(`/timetable-validation/runs/${id}/issues`, { params })).data },
};
export const reportsApi = {
  async definitions() { return (await api.get<ReportDefinition[]>("/reports/definitions")).data },
  async filterOptions() { return (await api.get<ReportFilterOptions>("/reports/filter-options")).data },
  async preview(payload: ReportRequest) { return (await api.post<ReportPreview>("/reports/preview", payload)).data },
  async export(payload: ReportRequest, format: "xlsx" | "csv" | "docx" | "pdf") {
    const response = await api.post<Blob>("/reports/export", payload, { params: { format }, responseType: "blob" });
    const disposition = String(response.headers["content-disposition"] ?? "");
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? `${payload.report_key}.${format}`;
    return { blob: response.data, filename };
  },
};
export const masterApi = {
  async departments() { return (await api.get<Page<Department>>("/departments", { params: { page_size: 100 } })).data },
  async programs(departmentId?: string) { return (await api.get<Page<Program>>("/programs", { params: { page_size: 100, department_id: departmentId } })).data },
  async sections(params: { program_id?: string; department_id?: string; academic_term_id?: string } = {}) { return (await api.get<Page<Section>>("/sections", { params: { page_size: 100, is_active: true, ...params } })).data },
  async workingDays() { return (await api.get<Page<WorkingDay>>("/working-days", { params: { page_size: 100, is_active: true } })).data },
  async classrooms(owningDepartmentId?: string) { return (await api.get<Page<Classroom>>("/classrooms", { params: { page_size: 100, is_active: true, owning_department_id: owningDepartmentId } })).data },
  async laboratories(owningDepartmentId?: string) { return (await api.get<Page<Laboratory>>("/laboratories", { params: { page_size: 100, is_active: true, owning_department_id: owningDepartmentId } })).data },
  async faculty(search?: string, departmentId?: string) { return (await api.get<Page<Faculty>>("/faculty", { params: { page_size: 100, is_active: true, search, department_id: departmentId } })).data },
  async courses(search?: string) { return (await api.get<Page<Course>>("/courses", { params: { page_size: 100, is_active: true, search } })).data },
  async studentBatches(sectionId?: string) { return (await api.get<Page<StudentBatch>>("/student-batches", { params: { page_size: 100, is_active: true, section_id: sectionId } })).data },
  async workload(params: { faculty_id?: string; academic_term_id?: string; department_id?: string } = {}) { return (await api.get<WorkloadPreview[]>("/faculty-allocations/workload-preview", { params })).data },
};
export const versionOperationsApi = {
  async buildInput(id: string) { return (await api.post<SolverInputSnapshot>(`/timetable-versions/${id}/build-solver-input`)).data },
  async solverInput(id: string) { return (await api.get<SolverInputSnapshot>(`/timetable-versions/${id}/solver-input`)).data },
  async solve(id: string, payload: { optimization_profile: string; time_limit_seconds?: number; random_seed: number; weight_overrides: Record<string, number> }) { return (await api.post<SolverRun>(`/timetable-versions/${id}/solve`, payload)).data },
  async copy(id: string, payload: { version_name: string; source_type: "MANUAL_COPY" }) { return (await api.post<TimetableVersion>(`/timetable-versions/${id}/copy`, payload)).data },
  async compare(id: string, otherId: string) { return (await api.get<VersionComparison>(`/timetable-versions/${id}/compare/${otherId}`)).data },
  async free(id: string, kind: "faculty" | "classrooms" | "laboratories", workingDayId: string, periodNumber: number) { return (await api.get<FreeResourceResponse>(`/timetable-versions/${id}/free-${kind}`, { params: { working_day_id: workingDayId, period_number: periodNumber } })).data },
};
export const entryOperationsApi = {
  async move(id: string, payload: { working_day_id: string; period_number: number; classroom_id?: string | null; laboratory_id?: string | null; lock_after_move: boolean }) { return (await api.post<TimetableEntry>(`/timetable-entries/${id}/move`, payload)).data },
  async lock(id: string, reason?: string) { return (await api.post<TimetableEntry>(`/timetable-entries/${id}/lock`, { reason: reason || null })).data },
  async unlock(id: string, reason: string) { return (await api.post<TimetableEntry>(`/timetable-entries/${id}/unlock`, { reason })).data },
  async audit(id: string) { return (await api.get<EntryAudit[]>(`/timetable-entries/${id}/audit`)).data },
};
export async function listAcademicTerms() { return (await api.get<Page<AcademicTerm>>("/academic-terms", { params: { page_size: 100 } })).data }
