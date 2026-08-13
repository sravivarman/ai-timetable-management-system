"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Card, EmptyState, ErrorState, LoadingState, Modal, PageHeader, StatusBadge } from "@/components/ui";
import { listAcademicTerms, masterApi, validationApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { sectionLabel, sectionTerm } from "@/lib/section-labels";
import type { ValidationRun } from "@/lib/types";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/providers/toast-provider";

const scopes = ["COLLEGE", "DEPARTMENT", "PROGRAM", "SECTION"] as const;
const schema = z.object({ academic_term_id: z.string().uuid("Select an academic term"), scope_type: z.enum(scopes), department_id: z.string().optional(), program_id: z.string().optional(), section_id: z.string().optional() }).superRefine((value, context) => {
  const required = value.scope_type === "DEPARTMENT" ? "department_id" : value.scope_type === "PROGRAM" ? "program_id" : value.scope_type === "SECTION" ? "section_id" : null;
  for (const field of ["department_id", "program_id", "section_id"] as const) {
    if (field === required && !value[field]) context.addIssue({ code: "custom", path: [field], message: `${field.replace("_id", "")} is required for this scope` });
    if (field !== required && value[field]) context.addIssue({ code: "custom", path: [field], message: `${field.replace("_id", "")} must be empty for ${value.scope_type}` });
  }
});
type FormData = z.infer<typeof schema>;

export default function ValidationPage() {
  const client = useQueryClient();
  const { hasRole } = useAuth();
  const { notify } = useToast();
  const canRun = hasRole("Administrator", "System Administrator", "Timetable Coordinator", "HOD");
  const [filters, setFilters] = useState({ academic_term_id: "", scope_type: "", status: "", page: 1, page_size: 10 });
  const [selected, setSelected] = useState<ValidationRun | null>(null);
  const form = useForm<FormData>({ resolver: zodResolver(schema), defaultValues: { academic_term_id: "", scope_type: "COLLEGE", department_id: "", program_id: "", section_id: "" } });
  const scope = form.watch("scope_type");
  const terms = useQuery({ queryKey: queryKeys.academicTerms, queryFn: listAcademicTerms });
  const departments = useQuery({ queryKey: queryKeys.departments("validation"), queryFn: masterApi.departments, enabled: scope === "DEPARTMENT" });
  const programs = useQuery({ queryKey: queryKeys.programs("validation"), queryFn: () => masterApi.programs(), enabled: scope === "PROGRAM" });
  const sections = useQuery({ queryKey: queryKeys.sections("validation", form.watch("academic_term_id")), queryFn: () => masterApi.sections({ academic_term_id: form.getValues("academic_term_id") || undefined }), enabled: scope === "SECTION" });
  const listParams = { academic_term_id: filters.academic_term_id || undefined, scope_type: filters.scope_type || undefined, status: filters.status || undefined, page: filters.page, page_size: filters.page_size };
  const runs = useQuery({ queryKey: queryKeys.validationRuns(listParams), queryFn: () => validationApi.list(listParams) });
  const mutation = useMutation({ mutationFn: validationApi.run, onSuccess: (run) => { notify(`Validation completed with ${run.status}`); setSelected(run); void client.invalidateQueries({ queryKey: queryKeys.validationRunsRoot }); void client.invalidateQueries({ queryKey: queryKeys.dashboard }); }, onError: (error) => notify(apiErrorMessage(error), "error") });

  function changeScope(next: FormData["scope_type"]) {
    form.setValue("scope_type", next);
    form.setValue("department_id", ""); form.setValue("program_id", ""); form.setValue("section_id", "");
  }
  return <>
    <PageHeader title="Timetable prerequisite validation" description="Validate academic, allocation, facility, and schedule readiness before creating a solver version." />
    {canRun && <Card title="Run validation" className="mb-5"><form className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" onSubmit={form.handleSubmit((value) => mutation.mutate(cleanScope(value)))}>
      <Field label="Academic term" error={form.formState.errors.academic_term_id?.message}><select className="field" {...form.register("academic_term_id")}><option value="">Select term</option>{terms.data?.items.map((term) => <option key={term.id} value={term.id}>{term.academic_year} · {term.term_name}</option>)}</select></Field>
      <Field label="Scope" error={form.formState.errors.scope_type?.message}><select className="field" value={scope} onChange={(event) => changeScope(event.target.value as FormData["scope_type"])}>{scopes.map((item) => <option key={item}>{item}</option>)}</select></Field>
      {scope === "DEPARTMENT" && <Field label="Department" error={form.formState.errors.department_id?.message}><select className="field" {...form.register("department_id")}><option value="">Select department</option>{departments.data?.items.map((item) => <option key={item.id} value={item.id}>{item.department_code} · {item.department_name}</option>)}</select></Field>}
      {scope === "PROGRAM" && <Field label="Program" error={form.formState.errors.program_id?.message}><select className="field" {...form.register("program_id")}><option value="">Select program</option>{programs.data?.items.map((item) => <option key={item.id} value={item.id}>{item.program_code} · {item.program_name}</option>)}</select></Field>}
      {scope === "SECTION" && <Field label="Section" error={form.formState.errors.section_id?.message}><select className="field" {...form.register("section_id")}><option value="">Select section</option>{sections.data?.items.map((item) => <option key={item.id} value={item.id}>{sectionLabel(item, sectionTerm(item, terms.data?.items))}</option>)}</select></Field>}
      <div className="flex items-end"><button className="button-primary w-full" disabled={mutation.isPending}>{mutation.isPending ? "Validating…" : "Run validation"}</button></div>
    </form></Card>}
    <Card title="Validation history"><div className="mb-4 grid gap-3 md:grid-cols-4"><select aria-label="Filter academic term" className="field" value={filters.academic_term_id} onChange={(event) => setFilters({ ...filters, academic_term_id: event.target.value, page: 1 })}><option value="">All terms</option>{terms.data?.items.map((term) => <option key={term.id} value={term.id}>{term.academic_year} · {term.term_name}</option>)}</select><select aria-label="Filter scope" className="field" value={filters.scope_type} onChange={(event) => setFilters({ ...filters, scope_type: event.target.value, page: 1 })}><option value="">All scopes</option>{scopes.map((item) => <option key={item}>{item}</option>)}</select><select aria-label="Filter status" className="field" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value, page: 1 })}><option value="">All statuses</option>{["PASSED", "WARNING", "FAILED"].map((item) => <option key={item}>{item}</option>)}</select><select aria-label="Page size" className="field" value={filters.page_size} onChange={(event) => setFilters({ ...filters, page_size: Number(event.target.value), page: 1 })}>{[10, 20, 50].map((size) => <option key={size}>{size}</option>)}</select></div>
      {runs.isLoading ? <LoadingState /> : runs.isError ? <ErrorState message={apiErrorMessage(runs.error)} retry={() => void runs.refetch()} /> : !runs.data?.items.length ? <EmptyState title="No validation runs" /> : <><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Created", "Scope", "Status", "Checks", "Errors", "Warnings", "Action"].map((item) => <th key={item} className="px-3 py-3">{item}</th>)}</tr></thead><tbody className="divide-y">{runs.data.items.map((run) => <tr key={run.id}><td className="px-3 py-3">{new Date(run.created_at).toLocaleString()}</td><td className="px-3 py-3">{run.scope_type}</td><td className="px-3 py-3"><StatusBadge value={run.status} /></td><td className="px-3 py-3">{run.total_checks}</td><td className="px-3 py-3">{run.failed_checks}</td><td className="px-3 py-3">{run.warning_checks}</td><td className="px-3 py-3"><button className="text-sm font-semibold text-brand-700" onClick={() => setSelected(run)}>View issues</button></td></tr>)}</tbody></table></div><Pagination page={filters.page} pages={runs.data.pages} onPage={(page) => setFilters({ ...filters, page })} /></>}
    </Card>
    {selected && <ValidationDetail runId={selected.id} onClose={() => setSelected(null)} />}
  </>;
}

function ValidationDetail({ runId, onClose }: { runId: string; onClose(): void }) {
  const [page, setPage] = useState(1);
  const run = useQuery({ queryKey: queryKeys.validationRun(runId), queryFn: () => validationApi.get(runId) });
  const issues = useQuery({ queryKey: queryKeys.validationIssues(runId, { page }), queryFn: () => validationApi.issues(runId, { page, page_size: 10 }) });
  return <Modal title="Validation run details" onClose={onClose} wide>{run.isLoading ? <LoadingState /> : run.isError ? <ErrorState message={apiErrorMessage(run.error)} /> : <div className="mb-5 flex flex-wrap gap-3"><StatusBadge value={run.data!.status} /><span className="text-sm">{run.data!.passed_checks} passed</span><span className="text-sm text-red-700">{run.data!.failed_checks} errors</span><span className="text-sm text-amber-700">{run.data!.warning_checks} warnings</span></div>}{issues.isLoading ? <LoadingState /> : issues.isError ? <ErrorState message={apiErrorMessage(issues.error)} /> : !issues.data?.items.length ? <EmptyState title="No issues" detail="All applicable checks passed." /> : <><div className="space-y-3">{issues.data.items.map((issue) => <article key={issue.id} className="rounded-xl border p-4"><div className="flex flex-wrap items-center gap-2"><StatusBadge value={issue.severity} /><code className="text-xs font-semibold">{issue.issue_code}</code><time className="ml-auto text-xs text-slate-500">{new Date(issue.created_at).toLocaleString()}</time></div><p className="mt-2 text-sm">{issue.message}</p><p className="mt-2 break-all text-xs text-slate-500">{issue.entity_type ?? "General"}{issue.entity_id ? ` · ${issue.entity_id}` : ""}</p>{issue.details && <pre className="mt-2 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{JSON.stringify(issue.details, null, 2)}</pre>}</article>)}</div><Pagination page={page} pages={issues.data.pages} onPage={setPage} /></>}</Modal>;
}

function cleanScope(value: FormData) { return { academic_term_id: value.academic_term_id, scope_type: value.scope_type, ...(value.department_id ? { department_id: value.department_id } : {}), ...(value.program_id ? { program_id: value.program_id } : {}), ...(value.section_id ? { section_id: value.section_id } : {}) }; }
function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) { return <label className="block"><span className="label">{label}</span>{children}{error && <span className="mt-1 block text-xs text-red-600">{error}</span>}</label>; }
function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage(page: number): void }) { return <div className="mt-4 flex items-center justify-between text-sm"><button className="button-secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button><span>Page {page} of {Math.max(pages, 1)}</span><button className="button-secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button></div>; }
