"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { listAcademicTerms, masterApi, schedulingSlotApi, timetableApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import type { SchedulingMode } from "@/lib/types";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/providers/toast-provider";

const scopes = ["COLLEGE", "DEPARTMENT", "PROGRAM", "SECTION"] as const;
type Scope = typeof scopes[number];
type Draft = { name: string; academic_term_id: string; scope_type: Scope; scope_id: string; scheduling_mode: SchedulingMode; scheduling_slot_id: string };
const emptyDraft: Draft = { name: "", academic_term_id: "", scope_type: "COLLEGE", scope_id: "", scheduling_mode: "WEEKLY", scheduling_slot_id: "" };

export default function TimetablesPage() {
  const client = useQueryClient();
  const { hasRole } = useAuth();
  const { notify } = useToast();
  const canManage = hasRole("Administrator", "System Administrator", "Timetable Coordinator");
  const [page, setPage] = useState(1);
  const [term, setTerm] = useState("");
  const [scope, setScope] = useState("");
  const [mode, setMode] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const query = useQuery({ queryKey: ["timetables", page, term, scope, mode, status], queryFn: () => timetableApi.list({ page, page_size: 10, academic_term_id: term || undefined, scope_type: scope || undefined, scheduling_mode: mode || undefined, status: status || undefined }) });
  const terms = useQuery({ queryKey: ["academic-terms"], queryFn: listAcademicTerms });
  const departments = useQuery({ queryKey: ["departments", "timetable-create"], queryFn: masterApi.departments, enabled: canManage && draft.scope_type === "DEPARTMENT" });
  const programs = useQuery({ queryKey: ["programs", "timetable-create"], queryFn: () => masterApi.programs(), enabled: canManage && draft.scope_type === "PROGRAM" });
  const sections = useQuery({ queryKey: ["sections", "timetable-create", draft.academic_term_id], queryFn: () => masterApi.sections({ academic_term_id: draft.academic_term_id || undefined }), enabled: canManage && draft.scope_type === "SECTION" && Boolean(draft.academic_term_id) });
  const slots = useQuery({ queryKey: ["scheduling-slots", "timetable-create", draft.academic_term_id], queryFn: () => schedulingSlotApi.list({ academic_term_id: draft.academic_term_id, is_active: true }), enabled: canManage && draft.scheduling_mode === "SLOT_BASED" && Boolean(draft.academic_term_id) });
  const slotNames = useMemo(() => new Map(slots.data?.items.map((item) => [item.id, item.slot_code])), [slots.data]);
  const create = useMutation({
    mutationFn: () => {
      const scopeId = draft.scope_id || undefined;
      return timetableApi.create({
        academic_term_id: draft.academic_term_id,
        scope_type: draft.scope_type,
        ...(draft.scope_type === "DEPARTMENT" ? { department_id: scopeId } : {}),
        ...(draft.scope_type === "PROGRAM" ? { program_id: scopeId } : {}),
        ...(draft.scope_type === "SECTION" ? { section_id: scopeId } : {}),
        scheduling_mode: draft.scheduling_mode,
        ...(draft.scheduling_mode === "SLOT_BASED" ? { scheduling_slot_id: draft.scheduling_slot_id } : {}),
        name: draft.name.trim(),
      });
    },
    onSuccess: async () => { notify("Timetable created."); setDraft(emptyDraft); await client.invalidateQueries({ queryKey: ["timetables"] }); },
    onError: (error) => notify(apiErrorMessage(error), "error"),
  });
  const rows = query.data?.items.filter((item) => item.name.toLowerCase().includes(search.toLowerCase())) ?? [];
  const needsScopeId = draft.scope_type !== "COLLEGE";
  const createDisabled = create.isPending || !draft.name.trim() || !draft.academic_term_id || (needsScopeId && !draft.scope_id) || (draft.scheduling_mode === "SLOT_BASED" && !draft.scheduling_slot_id);

  return <>
    <PageHeader title="Timetables" description="Create and manage recurring Weekly or actual-date Slot-Based timetable plans." />
    {canManage && <Card title="Create timetable" className="mb-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label><span className="label">Name</span><input className="field" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
        <label><span className="label">Academic term</span><select className="field" value={draft.academic_term_id} onChange={(event) => setDraft({ ...draft, academic_term_id: event.target.value, scheduling_slot_id: "", scope_id: draft.scope_type === "SECTION" ? "" : draft.scope_id })}><option value="">Select term</option>{terms.data?.items.map((item) => <option key={item.id} value={item.id}>{item.academic_year} · {item.term_name}</option>)}</select></label>
        <label><span className="label">Scheduling mode</span><select className="field" value={draft.scheduling_mode} onChange={(event) => setDraft({ ...draft, scheduling_mode: event.target.value as SchedulingMode, scheduling_slot_id: "" })}><option value="WEEKLY">Weekly</option><option value="SLOT_BASED">Slot Based</option></select></label>
        {draft.scheduling_mode === "SLOT_BASED" && <label><span className="label">Scheduling Slot</span><select className="field" disabled={!draft.academic_term_id || slots.isLoading} value={draft.scheduling_slot_id} onChange={(event) => setDraft({ ...draft, scheduling_slot_id: event.target.value })}><option value="">{slots.isLoading ? "Loading Slots…" : "Select Slot"}</option>{slots.data?.items.map((item) => <option key={item.id} value={item.id}>{item.slot_code} · {item.slot_name} ({item.working_date_count} dates)</option>)}</select></label>}
        <label><span className="label">Scope</span><select className="field" value={draft.scope_type} onChange={(event) => setDraft({ ...draft, scope_type: event.target.value as Scope, scope_id: "" })}>{scopes.map((item) => <option key={item}>{item}</option>)}</select></label>
        {draft.scope_type === "DEPARTMENT" && <label><span className="label">Department</span><select className="field" value={draft.scope_id} onChange={(event) => setDraft({ ...draft, scope_id: event.target.value })}><option value="">Select department</option>{departments.data?.items.map((item) => <option key={item.id} value={item.id}>{item.department_code} · {item.department_name}</option>)}</select></label>}
        {draft.scope_type === "PROGRAM" && <label><span className="label">Program</span><select className="field" value={draft.scope_id} onChange={(event) => setDraft({ ...draft, scope_id: event.target.value })}><option value="">Select program</option>{programs.data?.items.map((item) => <option key={item.id} value={item.id}>{item.program_code} · {item.program_name}</option>)}</select></label>}
        {draft.scope_type === "SECTION" && <label><span className="label">Section</span><select className="field" value={draft.scope_id} onChange={(event) => setDraft({ ...draft, scope_id: event.target.value })}><option value="">Select section</option>{sections.data?.items.map((item) => <option key={item.id} value={item.id}>{item.section_code}</option>)}</select></label>}
      </div>
      <button className="button-primary mt-4" disabled={createDisabled} onClick={() => create.mutate()}>{create.isPending ? "Creating…" : "Create timetable"}</button>
    </Card>}
    <div className="panel mb-5 grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-6">
      <input className="field" aria-label="Search timetable name" placeholder="Search name…" value={search} onChange={(event) => setSearch(event.target.value)} />
      <select className="field" aria-label="Academic term" value={term} onChange={(event) => { setTerm(event.target.value); setPage(1); }}><option value="">All academic terms</option>{terms.data?.items.map((item) => <option key={item.id} value={item.id}>{item.academic_year} {item.term_name}</option>)}</select>
      <select className="field" aria-label="Scheduling mode" value={mode} onChange={(event) => { setMode(event.target.value); setPage(1); }}><option value="">All modes</option><option value="WEEKLY">Weekly</option><option value="SLOT_BASED">Slot Based</option></select>
      <select className="field" aria-label="Scope type" value={scope} onChange={(event) => { setScope(event.target.value); setPage(1); }}><option value="">All scopes</option>{scopes.map((item) => <option key={item}>{item}</option>)}</select>
      <select className="field" aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option>{["DRAFT", "GENERATED", "UNDER_REVIEW", "APPROVED", "PUBLISHED", "ARCHIVED"].map((item) => <option key={item}>{item}</option>)}</select>
      <button className="button-secondary" onClick={() => { setTerm(""); setScope(""); setMode(""); setStatus(""); setSearch(""); setPage(1); }}>Clear filters</button>
    </div>
    {query.isLoading ? <LoadingState /> : query.isError ? <ErrorState message={apiErrorMessage(query.error)} retry={() => void query.refetch()} /> : rows.length === 0 ? <EmptyState title="No timetables found" detail="Try changing the filters or create a timetable." /> : <div className="panel overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Name", "Mode", "Scope", "Status", "Active version", ""].map((label) => <th className="px-4 py-3" key={label || "action"}>{label}</th>)}</tr></thead><tbody className="divide-y">{rows.map((row) => <tr key={row.id} className="hover:bg-slate-50"><td className="px-4 py-4 font-medium">{row.name}</td><td className="px-4 py-4"><StatusBadge value={row.scheduling_mode ?? "WEEKLY"} />{row.scheduling_slot_id && <div className="mt-1 text-xs text-slate-500">{slotNames.get(row.scheduling_slot_id) ?? "Configured Slot"}</div>}</td><td className="px-4 py-4">{row.scope_type}</td><td className="px-4 py-4"><StatusBadge value={row.status} /></td><td className="px-4 py-4">{row.active_version_id ? <span className="text-emerald-700">Active</span> : "—"}</td><td className="px-4 py-4 text-right"><Link className="inline-flex items-center gap-1 font-semibold text-brand-700 hover:underline" href={`/timetables/${row.id}`}>Open <ExternalLink className="h-3.5 w-3.5" /></Link></td></tr>)}</tbody></table></div>}
    <div className="mt-4 flex items-center justify-between text-sm"><span>Page {query.data?.page ?? page} of {Math.max(query.data?.pages ?? 1, 1)} · {query.data?.total ?? 0} records</span><div className="flex gap-2"><button className="button-secondary p-2" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="h-4 w-4" /></button><button className="button-secondary p-2" aria-label="Next page" disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}><ChevronRight className="h-4 w-4" /></button></div></div>
  </>;
}
