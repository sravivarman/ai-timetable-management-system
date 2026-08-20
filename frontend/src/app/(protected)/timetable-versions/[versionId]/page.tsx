"use client";

import clsx from "clsx";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Copy } from "lucide-react";
import { ComparisonPanel } from "@/components/comparison-panel";
import { ConflictsPanel } from "@/components/conflicts-panel";
import { EntriesPanel } from "@/components/entries-panel";
import { QualityPanel, SolverRunsPanel } from "@/components/solver-quality-panel";
import { TimetableViewPanel, type TimetableViewType, type ViewOption } from "@/components/timetable-view-panel";
import { FreeResourcesPanel, VersionActions } from "@/components/version-actions";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { timetableApi, validationApi } from "@/lib/api";
import { masterDataApi, type MasterRecord } from "@/lib/master-data-api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { GridEntry, Timetable, TimetableEntry, TimetableGrid } from "@/lib/types";
import { useAuth } from "@/providers/auth-provider";
import { readableRecordLabel, validationRunLabel } from "@/lib/readable-labels";

const tabGroups = [
  { label: "Views", tabs: ["Section View", "Faculty View", "Classroom View", "Laboratory View", "Batch View"] },
  { label: "Review", tabs: ["Entries"] },
  { label: "Solver", tabs: ["Solver Runs", "Quality"] },
  { label: "Analysis", tabs: ["Conflicts", "Comparison", "Free Resources"] },
] as const;
type Tab = typeof tabGroups[number]["tabs"][number];

const viewTypes: Partial<Record<Tab, TimetableViewType>> = {
  "Section View": "section",
  "Faculty View": "faculty",
  "Classroom View": "classroom",
  "Laboratory View": "laboratory",
  "Batch View": "batch",
};

export default function VersionPage() {
  const { versionId } = useParams<{ versionId: string }>();
  const searchParams = useSearchParams(); const router = useRouter();
  const requestedTab = searchParams.get("view") as Tab | null;
  const [tab, setTab] = useState<Tab>(tabGroups.some((group) => group.tabs.some((value) => value === requestedTab)) ? requestedTab! : "Section View");
  const { hasRole } = useAuth();
  const isAdministrator = hasRole("Administrator", "System Administrator");
  const isOperationalReader = isAdministrator || hasRole("Timetable Coordinator", "HOD", "Dean", "Principal");
  const canManageEntries = isAdministrator || hasRole("Timetable Coordinator", "HOD");
  const canAudit = isOperationalReader;
  const version = useQuery({ queryKey: queryKeys.version(versionId), queryFn: () => timetableApi.version(versionId) });
  const timetable = useQuery({ queryKey: queryKeys.timetable(version.data?.timetable_id ?? ""), queryFn: () => timetableApi.get(version.data!.timetable_id), enabled: Boolean(version.data?.timetable_id) });
  const versions = useQuery({ queryKey: queryKeys.versions(version.data?.timetable_id ?? ""), queryFn: () => timetableApi.versions(version.data!.timetable_id), enabled: Boolean(version.data?.timetable_id) });
  const entries = useQuery({ queryKey: queryKeys.entries(versionId), queryFn: () => timetableApi.entries(versionId), enabled: isOperationalReader });
  const runs = useQuery({ queryKey: queryKeys.versionSolverRuns(versionId), queryFn: () => timetableApi.solverRuns(versionId), enabled: isOperationalReader });
  const conflicts = useQuery({ queryKey: queryKeys.conflicts(versionId), queryFn: () => timetableApi.conflicts(versionId), enabled: tab === "Conflicts", retry: false });
  const sectionId = timetable.data?.section_id ?? "";
  const sectionGrid = useQuery({ queryKey: queryKeys.sectionGrid(versionId, sectionId), queryFn: () => timetableApi.sectionGrid(versionId, sectionId), enabled: Boolean(sectionId) && isOperationalReader });
  const resourceEndpoints = ["/sections", "/faculty", "/classrooms", "/laboratories", "/student-batches"] as const;
  const resourceQueries = useQueries({ queries: resourceEndpoints.map((endpoint) => ({ queryKey: ["version-resource-labels", endpoint], queryFn: () => masterDataApi.lookup(endpoint), enabled: isOperationalReader, staleTime: 60_000, retry: false })) });
  const validationRun = useQuery({ queryKey: queryKeys.validationRun(version.data?.validation_run_id ?? ""), queryFn: () => validationApi.get(version.data!.validation_run_id), enabled: Boolean(version.data?.validation_run_id), retry: false });

  if (version.isLoading) return <LoadingState />;
  if (version.isError) return <ErrorState message={apiErrorMessage(version.error)} />;
  if (timetable.isLoading) return <LoadingState />;
  if (timetable.isError) return <ErrorState message={apiErrorMessage(timetable.error)} />;
  const item = version.data!;
  const parent = timetable.data!;
  const immutable = ["APPROVED", "PUBLISHED", "ARCHIVED"].includes(parent.status);
  const entryDisabledReason = !item.is_active ? "This historical version is inactive." : item.is_locked ? "This version is locked. Entry changes are disabled." : immutable ? `${parent.status.replaceAll("_", " ")} timetables are read-only.` : undefined;
  const resources = Object.fromEntries(resourceEndpoints.map((endpoint, index) => [endpoint, resourceQueries[index].data ?? []])) as Record<string, MasterRecord[]>;
  const options = resourceOptions(entries.data?.items ?? [], sectionGrid.data, parent, resources);
  const qualityLabels = Object.fromEntries(Object.values(options).flat().map((option) => [option.id, option.label]));
  const selectedView = viewTypes[tab];
  const latestSuccessfulRun = runs.data?.items.find((run) => run.status === "OPTIMAL" || run.status === "FEASIBLE");
  const orderedVersions = [...(versions.data?.items ?? [])].sort((a, b) => a.version_number - b.version_number); const position = orderedVersions.findIndex((candidate) => candidate.id === item.id); const previous = position > 0 ? orderedVersions[position - 1] : undefined; const next = position >= 0 ? orderedVersions[position + 1] : undefined;
  const selectTab = (value: Tab) => { setTab(value); const params = new URLSearchParams(searchParams); params.set("view", value); router.replace(`/timetable-versions/${versionId}?${params.toString()}`, { scroll: false }); };

  return <>
    <PageHeader title={`Timetable version ${item.version_number}`} description={item.version_name ?? `Version ${item.version_number}`} actions={<div className="flex flex-wrap items-center gap-2">{previous && <Link className="button-secondary" href={`/timetable-versions/${previous.id}`}>← Version {previous.version_number}</Link>}{next && <Link className="button-secondary" href={`/timetable-versions/${next.id}`}>Version {next.version_number} →</Link>}<StatusBadge value={parent.status} /><StatusBadge value={item.solver_status} />{item.is_active && <StatusBadge value="ACTIVE" />}{item.is_locked && <StatusBadge value="LOCKED" />}</div>} />
    <Card title="Version metadata" className="mb-5"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Metadata label="Version ID" value={item.id} /><Metadata label="Timetable" value={parent.name} /><Metadata label="Version name" value={item.version_name ?? "—"} /><Metadata label="Version number" value={String(item.version_number)} /><Metadata label="Source" value={item.source_type} /><Metadata label="Validation run" value={validationRun.data ? validationRunLabel(validationRun.data) : validationRun.isLoading ? "Loading validation run…" : "Validation metadata unavailable"} copyValue={item.validation_run_id} /><Metadata label="Created" value={new Date(item.created_at).toLocaleString()} /><Metadata label="Updated" value={new Date(item.updated_at).toLocaleString()} /></div><Link className="mt-4 inline-flex text-sm font-semibold text-brand-700 underline" href={`/timetables/${parent.id}`}>Open timetable workflow and status history</Link></Card>
    {!item.is_active || item.is_locked || immutable ? <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><strong>Read-only safeguards are active.</strong> Solver execution and entry mutations are disabled, while metadata, solver input, history, quality, comparison, audit, conflicts, free resources, and rendered views remain available according to your role.</div> : null}
    <VersionActions version={item} timetable={parent} />

    <nav className="mb-5 space-y-3 rounded-xl border bg-white p-3" aria-label="Timetable version workspace">
      {tabGroups.map((group) => <div key={group.label} className="flex flex-wrap items-center gap-2"><span className="w-20 text-xs font-semibold uppercase tracking-wide text-slate-400">{group.label}</span>{group.tabs.map((value) => <button key={value} className={clsx("rounded-lg px-3 py-2 text-sm font-medium", tab === value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800")} aria-current={tab === value ? "page" : undefined} onClick={() => selectTab(value)}>{value}</button>)}</div>)}
    </nav>

    {selectedView ? <Card title={tab}><TimetableViewPanel versionId={versionId} viewType={selectedView} initialResourceId={searchParams.get("resource_id") ?? (selectedView === "section" ? sectionId : "")} options={options[selectedView]} /></Card> : null}
    {tab === "Entries" && <Card title="Manual review entries">{!isOperationalReader ? <EmptyState title="Entry access is not available for your role" /> : entries.isLoading ? <LoadingState /> : entries.isError ? <ErrorState message={apiErrorMessage(entries.error)} retry={() => void entries.refetch()} /> : <EntriesPanel entries={entries.data?.items ?? []} grid={sectionGrid.data} versionId={versionId} editable={canManageEntries} disabledReason={entryDisabledReason} canAudit={canAudit} />}</Card>}
    {tab === "Solver Runs" && <Card title="Solver history">{!isOperationalReader ? <EmptyState title="Solver history is not available for your role" /> : runs.isLoading ? <LoadingState /> : runs.isError ? <ErrorState message={apiErrorMessage(runs.error)} /> : <SolverRunsPanel runs={runs.data?.items ?? []} />}</Card>}
    {tab === "Quality" && <Card title="Solver quality">{!isOperationalReader ? <EmptyState title="Solver quality is not available for your role" /> : runs.isLoading ? <LoadingState /> : <QualityPanel runId={latestSuccessfulRun?.id} labels={qualityLabels} />}</Card>}
    {tab === "Conflicts" && <Card title="Conflict analysis">{conflicts.isLoading ? <LoadingState /> : conflicts.isError ? <ErrorState message={apiErrorMessage(conflicts.error)} retry={() => void conflicts.refetch()} /> : <ConflictsPanel report={conflicts.data!} entries={entries.data?.items} grid={sectionGrid.data} />}</Card>}
    {tab === "Comparison" && <Card title="Compare versions"><ComparisonPanel version={item} /></Card>}
    {tab === "Free Resources" && <FreeResourcesPanel versionId={versionId} workingDays={sectionGrid.data?.days.map((day) => ({ id: day.working_day_id, actualDate: day.actual_date, name: day.actual_date ? `${formatDate(day.actual_date)} · ${day.day_name}` : day.day_name }))} />}
  </>;
}

function Metadata({ label, value, copyValue }: { label: string; value: string; copyValue?: string }) { const copied = copyValue ?? (label.includes("ID") ? value : undefined); return <div><p className="text-xs text-slate-500">{label}</p><div className="mt-1 flex items-start gap-1"><p className="break-all text-sm font-semibold">{value}</p>{copied && <button className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-brand-700 print:hidden" aria-label={`Copy ${label} ID`} title={`Copy ${label} ID`} onClick={() => void navigator.clipboard.writeText(copied)}><Copy className="h-3.5 w-3.5" /></button>}</div></div>; }

function resourceOptions(entries: TimetableEntry[], grid: TimetableGrid | undefined, timetable: Timetable, resources: Record<string, MasterRecord[]>): Record<TimetableViewType, ViewOption[]> {
  const details = new Map<string, GridEntry>();
  for (const day of grid?.days ?? []) for (const entry of day.entries) details.set(entry.entry_id, entry);
  const values: Record<TimetableViewType, Map<string, string>> = { section: new Map(), faculty: new Map(), classroom: new Map(), laboratory: new Map(), batch: new Map() };
  const maps = { section: new Map((resources["/sections"] ?? []).map((row) => [row.id, readableRecordLabel("/sections", row)])), faculty: new Map((resources["/faculty"] ?? []).map((row) => [row.id, readableRecordLabel("/faculty", row)])), classroom: new Map((resources["/classrooms"] ?? []).map((row) => [row.id, readableRecordLabel("/classrooms", row)])), laboratory: new Map((resources["/laboratories"] ?? []).map((row) => [row.id, readableRecordLabel("/laboratories", row)])), batch: new Map((resources["/student-batches"] ?? []).map((row) => [row.id, readableRecordLabel("/student-batches", row)])) };
  if (timetable.section_id) values.section.set(timetable.section_id, maps.section.get(timetable.section_id) ?? "Scoped section");
  for (const entry of entries) {
    const detail = details.get(entry.id);
    values.section.set(entry.section_id, maps.section.get(entry.section_id) ?? detail?.section_code ?? "Section metadata unavailable");
    if (entry.faculty_id) values.faculty.set(entry.faculty_id, [detail?.faculty_code, detail?.faculty_name].filter(Boolean).join(" · ") || maps.faculty.get(entry.faculty_id) || "Faculty metadata unavailable");
    if (entry.classroom_id) values.classroom.set(entry.classroom_id, detail?.classroom_room_number ?? maps.classroom.get(entry.classroom_id) ?? "Classroom metadata unavailable");
    if (entry.laboratory_id) values.laboratory.set(entry.laboratory_id, [detail?.laboratory_code, detail?.laboratory_name].filter(Boolean).join(" · ") || maps.laboratory.get(entry.laboratory_id) || "Laboratory metadata unavailable");
    if (entry.student_batch_id) values.batch.set(entry.student_batch_id, detail?.batch_name ?? maps.batch.get(entry.student_batch_id) ?? "Batch metadata unavailable");
  }
  return Object.fromEntries(Object.entries(values).map(([type, map]) => [type, Array.from(map, ([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label))])) as Record<TimetableViewType, ViewOption[]>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`)); }
