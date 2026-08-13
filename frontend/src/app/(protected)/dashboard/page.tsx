"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, CalendarCheck, CalendarDays, CheckCircle2, Clock, FileClock, Gauge, Layers3 } from "lucide-react";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { listAcademicTerms, solverApi, timetableApi, validationApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { SolverRun, Timetable } from "@/lib/types";

export default function DashboardPage() {
  const query = useQuery({ queryKey: queryKeys.dashboard, queryFn: loadDashboard });
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState message="Dashboard data could not be loaded." retry={() => void query.refetch()} />;
  const data = query.data!; const solverDetails = describeSolver(data.latestSolver, data.solverUnavailable);
  const cards = [
    { label: "Active academic term", value: data.active ? `${data.active.academic_year} · ${data.active.term_name}` : "Not configured", icon: CalendarCheck },
    { label: "Timetables", value: String(data.timetables.length), icon: CalendarDays }, { label: "Published", value: String(data.counts.PUBLISHED ?? 0), icon: CheckCircle2 },
    { label: "Draft", value: String(data.counts.DRAFT ?? 0), icon: FileClock }, { label: "Under review", value: String(data.counts.UNDER_REVIEW ?? 0), icon: Activity },
    { label: "Approved", value: String(data.counts.APPROVED ?? 0), icon: CheckCircle2 }, { label: "Active versions", value: String(data.activeVersions), icon: Layers3 },
    { label: "Latest validation", value: data.latestValidation?.status ?? "No runs", icon: Activity, badge: true },
    { label: "Latest solver", value: solverDetails.status, detail: solverDetails.detail, icon: Gauge, badge: Boolean(data.latestSolver) },
    { label: "Average quality", value: data.averageQuality == null ? "Not reported" : data.averageQuality.toFixed(1), icon: Gauge },
    { label: "Average runtime", value: data.averageRuntime == null ? "Not reported" : `${data.averageRuntime.toFixed(2)}s`, icon: Clock },
    { label: "Conflict count", value: String(data.conflicts), icon: AlertTriangle },
  ];
  return <><PageHeader title="Dashboard" description="Current academic planning, workflow, solver quality, and timetable health." actions={<button className="button-secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? "Refreshing…" : "Refresh dashboard"}</button>} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ label, value, detail, icon: Icon, badge }) => <Card key={label}><div className="flex items-start justify-between gap-3"><div><p className="text-sm text-slate-500">{label}</p><div className="mt-3 text-2xl font-bold">{badge ? <StatusBadge value={value} /> : value}</div>{detail && <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{detail}</p>}</div><span className="rounded-lg bg-brand-50 p-3 text-brand-700 dark:bg-slate-800 dark:text-blue-300"><Icon className="h-5 w-5" /></span></div></Card>)}</div>
    <div className="mt-5 grid gap-5 lg:grid-cols-2"><Card title="Recently updated timetables">{!data.recent.length ? <EmptyState title="No timetables" /> : <ul className="divide-y dark:divide-slate-700">{data.recent.map((item) => <li key={item.id} className="flex items-center justify-between gap-3 py-3"><div><Link className="font-semibold text-brand-700 hover:underline dark:text-blue-300" href={`/timetables/${item.id}`}>{item.name}</Link><p className="mt-1 text-xs text-slate-500">Updated {new Date(item.updated_at).toLocaleString()}</p></div><StatusBadge value={item.status} /></li>)}</ul>}</Card><Card title="Recent workflow actions">{!data.actions.length ? <EmptyState title="No workflow actions" detail="Workflow history will appear as timetables are reviewed and published." /> : <ul className="divide-y dark:divide-slate-700">{data.actions.map((action, index) => <li key={`${action.created_at}-${index}`} className="py-3"><div className="flex items-center justify-between gap-3"><span className="text-sm font-semibold">{action.from_status.replaceAll("_", " ")} → {action.to_status.replaceAll("_", " ")}</span><time className="text-xs text-slate-500">{new Date(action.created_at).toLocaleString()}</time></div>{action.reason && <p className="mt-1 text-xs text-slate-500">{action.reason}</p>}</li>)}</ul>}</Card></div>
  </>;
}

async function loadDashboard() {
  const [termResult, timetableResult, latestSolverResult, solverPageResult, validationResult] = await Promise.all([settle(listAcademicTerms()), settle(timetableApi.list({ page_size: 100 })), settle(solverApi.list({ page: 1, page_size: 1 })), settle(solverApi.list({ page: 1, page_size: 100 })), settle(validationApi.list({ page: 1, page_size: 1 }))]);
  const terms = termResult.value?.items ?? []; const timetables = timetableResult.value?.items ?? []; const recent = [...timetables].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5); const activeIds = timetables.map((item) => item.active_version_id).filter(Boolean) as string[];
  const conflictResults = await Promise.all(activeIds.slice(0, 20).map((id) => settle(timetableApi.conflicts(id))));
  const historyResults = await Promise.all(recent.map((item) => settle(timetableApi.history(item.id))));
  const solverRuns = solverPageResult.value?.items ?? []; const qualityValues = solverRuns.map(qualityOf).filter((value): value is number => value != null); const runtimeValues = solverRuns.map((run) => run.runtime_seconds).filter((value): value is number => value != null);
  return { active: terms.find((term) => term.is_current) ?? terms.find((term) => term.is_active), timetables, recent, counts: countStatuses(timetables), activeVersions: activeIds.length, latestValidation: validationResult.value?.items[0], latestSolver: latestSolverResult.value?.items[0], solverUnavailable: !latestSolverResult.value, averageQuality: average(qualityValues), averageRuntime: average(runtimeValues), conflicts: conflictResults.reduce((total, result) => total + (result.value?.summary.total ?? result.value?.conflicts.length ?? 0), 0), actions: historyResults.flatMap((result) => result.value ?? []).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 8) };
}
function countStatuses(items: Timetable[]) { return items.reduce<Record<string, number>>((counts, item) => ({ ...counts, [item.status]: (counts[item.status] ?? 0) + 1 }), {}); }
async function settle<T>(promise: Promise<T>): Promise<{ value?: T }> { try { return { value: await promise }; } catch { return {}; } }
function average(values: number[]) { return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : undefined; }
function qualityOf(run: SolverRun) { const stats = run.statistics_json ?? {}; return numberValue(asRecord(stats.quality_metrics).quality_score) ?? numberValue(stats.solution_quality_score); }
function describeSolver(solver: SolverRun | undefined, unavailable: boolean) { if (unavailable) return { status: "Unavailable", detail: undefined }; if (!solver) return { status: "No runs", detail: undefined }; const statistics = solver.statistics_json ?? {}; const qualityMetrics = asRecord(statistics.quality_metrics); const profile = textValue(statistics.optimization_profile) ?? "Not reported"; const quality = numberValue(qualityMetrics.quality_score) ?? numberValue(statistics.solution_quality_score); const runtime = solver.runtime_seconds == null ? "Not reported" : `${solver.runtime_seconds.toFixed(2)}s`; return { status: solver.status, detail: `Profile ${profile} · Quality ${quality ?? "Not reported"} · Runtime ${runtime}` }; }
function asRecord(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function textValue(value: unknown) { return typeof value === "string" ? value : undefined; }
function numberValue(value: unknown) { return typeof value === "number" ? value : undefined; }
