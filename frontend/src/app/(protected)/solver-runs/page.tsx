"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Card, EmptyState, ErrorState, LoadingState, Modal, PageHeader, StatusBadge } from "@/components/ui";
import { SearchableSelect } from "@/components/searchable-select";
import { solverApi, timetableApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { solverRunLabel, timetableVersionLabel } from "@/lib/readable-labels";

export default function SolverRunsPage() {
  const [filters, setFilters] = useState({ timetable_version_id: "", status: "", page: 1, page_size: 20 });
  const [selected, setSelected] = useState("");
  const timetables = useQuery({ queryKey: ["solver-run-timetables"], queryFn: () => timetableApi.list({ page: 1, page_size: 100 }) });
  const versionQueries = useQueries({ queries: (timetables.data?.items ?? []).map((item) => ({ queryKey: queryKeys.versions(item.id), queryFn: () => timetableApi.versions(item.id) })) });
  const versions = useMemo(() => versionQueries.flatMap((query) => query.data?.items ?? []), [versionQueries]);
  const versionOptions = versions.map((version) => ({ value: version.id, label: timetableVersionLabel(version) }));
  const versionLabels = new Map(versionOptions.map((item) => [item.value, item.label]));
  const params = { timetable_version_id: filters.timetable_version_id || undefined, status: filters.status || undefined, page: filters.page, page_size: filters.page_size };
  const query = useQuery({ queryKey: queryKeys.solverRuns(params), queryFn: () => solverApi.list(params) });
  const selectedRun = query.data?.items.find((item) => item.id === selected);
  return <><PageHeader title="Solver runs" description="Review persisted solver execution history across all timetable versions." /><Card>
    <div className="mb-4 grid gap-3 md:grid-cols-3"><SearchableSelect label="Timetable version" value={filters.timetable_version_id} options={versionOptions} loading={timetables.isLoading || versionQueries.some((item) => item.isLoading)} error={timetables.isError ? apiErrorMessage(timetables.error) : undefined} emptyMessage="No readable timetable versions available" onChange={(value) => setFilters({ ...filters, timetable_version_id: value, page: 1 })} /><select aria-label="Solver status" className="field" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value, page: 1 })}><option value="">All statuses</option>{["OPTIMAL", "FEASIBLE", "INFEASIBLE", "FAILED"].map((status) => <option key={status}>{status}</option>)}</select><select aria-label="Page size" className="field" value={filters.page_size} onChange={(event) => setFilters({ ...filters, page_size: Number(event.target.value), page: 1 })}>{[10, 20, 50].map((size) => <option key={size}>{size}</option>)}</select></div>
    {query.isLoading ? <LoadingState /> : query.isError ? <ErrorState message={apiErrorMessage(query.error)} retry={() => void query.refetch()} /> : !query.data?.items.length ? <EmptyState title="No solver runs" /> : <><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Run", "Version", "Status", "Profile", "Runtime", "Quality", "Entries", "Created"].map((heading) => <th key={heading} className="px-3 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y">{query.data.items.map((run, index) => { const stats = run.statistics_json ?? {}; const quality = readNumber(readRecord(stats.quality_metrics).quality_score) ?? readNumber(stats.solution_quality_score); const ordinal = query.data.total - ((filters.page - 1) * filters.page_size) - index; return <tr key={run.id} className="cursor-pointer hover:bg-slate-50" tabIndex={0} onClick={() => setSelected(run.id)} onKeyDown={(event) => { if (event.key === "Enter") setSelected(run.id); }}><td className="px-3 py-3 font-medium">{solverRunLabel(run, ordinal)}</td><td className="px-3 py-3">{versionLabels.get(run.timetable_version_id) ?? "Version metadata unavailable"}</td><td className="px-3 py-3"><StatusBadge value={run.status} /></td><td className="px-3 py-3">{readText(stats.optimization_profile) ?? "—"}</td><td className="px-3 py-3">{run.runtime_seconds == null ? "—" : `${run.runtime_seconds.toFixed(2)}s`}</td><td className="px-3 py-3">{quality ?? "—"}</td><td className="px-3 py-3">{run.generated_entry_count}</td><td className="px-3 py-3">{new Date(run.created_at).toLocaleString()}</td></tr>; })}</tbody></table></div><div className="mt-4 flex justify-between"><button className="button-secondary" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Previous</button><span className="text-sm">Page {filters.page} of {Math.max(query.data.pages, 1)}</span><button className="button-secondary" disabled={filters.page >= query.data.pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Next</button></div></>}
  </Card>{selected && <SolverRunDetail runId={selected} label={selectedRun ? solverRunLabel(selectedRun) : "Solver run"} onClose={() => setSelected("")} />}</>;
}

function SolverRunDetail({ runId, label, onClose }: { runId: string; label: string; onClose(): void }) {
  const run = useQuery({ queryKey: queryKeys.solverRun(runId), queryFn: () => solverApi.get(runId) });
  const quality = useQuery({ queryKey: queryKeys.quality(runId), queryFn: () => solverApi.quality(runId), retry: false });
  return <Modal title={`${label} details`} onClose={onClose} wide>{run.isLoading ? <LoadingState /> : run.isError ? <ErrorState message={apiErrorMessage(run.error)} /> : <div className="grid gap-3 sm:grid-cols-4"><Metric label="Status"><StatusBadge value={run.data!.status} /></Metric><Metric label="Runtime" value={run.data!.runtime_seconds == null ? "—" : `${run.data!.runtime_seconds!.toFixed(2)}s`} /><Metric label="Generated entries" value={String(run.data!.generated_entry_count)} /><Metric label="Objective" value={run.data!.objective_value == null ? "—" : String(run.data!.objective_value)} /></div>}{quality.isLoading ? <LoadingState /> : quality.isError ? <ErrorState message={apiErrorMessage(quality.error)} /> : <div className="mt-5"><div className="grid gap-3 sm:grid-cols-3"><Metric label="Profile" value={quality.data!.optimization_profile} /><Metric label="Quality score" value={String(quality.data!.quality_score)} /><Metric label="Total penalty" value={String(quality.data!.total_penalty)} /></div><h3 className="mb-2 mt-5 font-semibold">Objective breakdown</h3><div className="grid gap-2 sm:grid-cols-2">{Object.entries(quality.data!.objective_breakdown).map(([name, value]) => <div key={name} className="flex justify-between rounded bg-slate-50 px-3 py-2 text-sm"><span>{name.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div></div>}</Modal>;
}

function Metric({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) { return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><div className="mt-1 font-semibold">{children ?? value}</div></div>; }
function readRecord(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function readText(value: unknown) { return typeof value === "string" ? value : undefined; }
function readNumber(value: unknown) { return typeof value === "number" ? value : undefined; }
