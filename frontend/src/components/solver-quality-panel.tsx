"use client";

import { useQuery } from "@tanstack/react-query";
import { timetableApi } from "@/lib/api";
import type { SolverRun } from "@/lib/types";
import { Card, EmptyState, ErrorState, LoadingState, StatusBadge } from "@/components/ui";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { isUuid } from "@/lib/readable-labels";

export function SolverRunsPanel({ runs }: { runs: SolverRun[] }) {
  if (!runs.length) return <EmptyState title="No solver runs" />;
  return <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm">
    <thead className="bg-slate-50"><tr>{["Run", "Status", "Runtime", "Objective", "Entries", "Profile", "Quality", "Created"].map((item) => <th key={item} className="px-3 py-3">{item}</th>)}</tr></thead>
    <tbody className="divide-y">{runs.map((run, index) => {
      const stats = run.statistics_json ?? {};
      return <tr key={run.id}><td className="px-3 py-3 font-medium">Run #{runs.length - index}</td><td className="px-3 py-3"><StatusBadge value={run.status} /></td><td className="px-3 py-3">{run.runtime_seconds?.toFixed(2) ?? "—"}s</td><td className="px-3 py-3">{run.objective_value ?? "—"}</td><td className="px-3 py-3">{run.generated_entry_count}</td><td className="px-3 py-3">{String(stats.optimization_profile ?? "—")}</td><td className="px-3 py-3">{String(stats.solution_quality_score ?? "—")}</td><td className="px-3 py-3">{new Date(run.created_at).toLocaleString()}</td></tr>;
    })}</tbody>
  </table></div>;
}

export function QualityPanel({ runId, labels = {} }: { runId?: string; labels?: Record<string, string> }) {
  const query = useQuery({ queryKey: queryKeys.quality(runId ?? ""), queryFn: () => timetableApi.quality(runId!), enabled: Boolean(runId), retry: false });
  if (!runId) return <EmptyState title="No solver run selected" detail="Quality metrics appear after a successful optimized solve." />;
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState message={apiErrorMessage(query.error)} />;
  const quality = query.data!;
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-3"><Card><p className="text-sm text-slate-500">Quality score</p><p className="mt-2 text-3xl font-bold text-brand-700">{quality.quality_score}</p></Card><Card><p className="text-sm text-slate-500">Total penalty</p><p className="mt-2 text-3xl font-bold">{quality.total_penalty}</p></Card><Card><p className="text-sm text-slate-500">Profile</p><p className="mt-2"><StatusBadge value={quality.optimization_profile} /></p></Card></div>
    <MetricTable title="Objective breakdown" data={quality.objective_breakdown} labels={labels} />
    <div className="grid gap-5 lg:grid-cols-2"><MetricTable title="Faculty idle gaps" data={quality.faculty_idle_gap_counts} labels={labels} /><MetricTable title="Section idle gaps" data={quality.section_idle_gap_counts} labels={labels} /><NestedMetric title="Faculty daily loads" data={quality.faculty_daily_loads} labels={labels} /><NestedMetric title="Section daily loads" data={quality.section_daily_loads} labels={labels} /><NestedMetric title="First / last counts" data={quality.faculty_first_last_counts} labels={labels} /><NestedMetric title="Course distribution" data={quality.course_day_distribution} labels={labels} /><NestedMetric title="Laboratory distribution" data={quality.laboratory_day_distribution} labels={labels} /></div>
  </div>;
}

function MetricTable({ title, data, labels }: { title: string; data: Record<string, number>; labels: Record<string, string> }) {
  return <Card title={title}><div className="divide-y">{Object.entries(data).map(([key, value]) => <div key={key} className="flex justify-between gap-4 py-2 text-sm"><span className="text-slate-600">{metricLabel(key, labels)}</span><strong>{value}</strong></div>)}</div></Card>;
}

function NestedMetric({ title, data, labels }: { title: string; data: Record<string, Record<string, number>>; labels: Record<string, string> }) {
  return <Card title={title}><div className="space-y-3">{Object.entries(data).map(([key, values]) => <div key={key}><p className="truncate text-xs font-semibold text-slate-500" title={metricLabel(key, labels)}>{metricLabel(key, labels)}</p><p className="mt-1 text-sm">{Object.values(values).join(" · ") || "—"}</p></div>)}</div></Card>;
}

function metricLabel(value: string, labels: Record<string, string>) {
  return labels[value] ?? (isUuid(value) ? "Resource metadata unavailable" : value.replaceAll("_", " "));
}
