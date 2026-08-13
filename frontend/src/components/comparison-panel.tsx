"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { timetableApi, versionOperationsApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { apiErrorMessage } from "@/lib/api-client";
import type { TimetableVersion } from "@/lib/types";
import { isUuid, timetableVersionLabel } from "@/lib/readable-labels";

export function ComparisonPanel({ version }: { version: TimetableVersion }) {
  const [otherId, setOtherId] = useState("");
  const versions = useQuery({ queryKey: queryKeys.comparisonVersions(version.timetable_id), queryFn: () => timetableApi.versions(version.timetable_id) });
  const comparison = useQuery({ queryKey: queryKeys.comparison(version.id, otherId), queryFn: () => versionOperationsApi.compare(version.id, otherId), enabled: Boolean(otherId) });
  return <div><label className="block max-w-md"><span className="label">Compare with version</span><select className="field" value={otherId} onChange={(event) => setOtherId(event.target.value)}><option value="">Select another version</option>{versions.data?.items.filter((item) => item.id !== version.id).map((item) => <option key={item.id} value={item.id}>{timetableVersionLabel(item)}</option>)}</select></label>{!otherId ? <div className="mt-5"><EmptyState title="Select a version to compare" /></div> : comparison.isLoading ? <LoadingState /> : comparison.isError ? <ErrorState message={apiErrorMessage(comparison.error)} /> : <div className="mt-5"><div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">{Object.entries(comparison.data!.summary).map(([name, value]) => <div key={name} className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{name.replaceAll("_", " ")}</p><strong className="text-xl">{value}</strong></div>)}</div>{[["Added entries", comparison.data!.added_entries], ["Removed entries", comparison.data!.removed_entries], ["Moved entries", comparison.data!.moved_entries], ["Faculty changes", comparison.data!.faculty_changes], ["Facility changes", comparison.data!.facility_changes], ["Lock-state changes", comparison.data!.lock_state_changes]].map(([title, rows]) => <ComparisonSection key={String(title)} title={String(title)} rows={rows as Record<string, unknown>[]} />)}</div>}</div>;
}

function ComparisonSection({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  return <section className="mt-5"><h3 className="mb-2 font-semibold">{title}</h3><div className="space-y-2">{rows.map((row, index) => { const from = record(row.from); const to = record(row.to); return <article key={index} className="rounded-lg border p-3 text-sm">{Object.keys(from).length || Object.keys(to).length ? <div className="grid gap-3 sm:grid-cols-2"><Diff title="Before" value={from} /><Diff title="After" value={to} /></div> : <Diff title="Entry" value={row} />}</article>; })}</div></section>;
}

function Diff({ title, value }: { title: string; value: Record<string, unknown> }) {
  const visible = Object.entries(value).filter(([key, item]) => key !== "id" && !key.endsWith("_id") && !key.endsWith("_ids") && !isUuid(String(item ?? "")));
  return <div><p className="mb-1 text-xs font-semibold uppercase text-slate-500">{title}</p>{visible.length ? <dl className="grid grid-cols-2 gap-1">{visible.map(([key, item]) => <div key={key} className="contents"><dt className="text-slate-500">{key.replaceAll("_", " ")}</dt><dd className="font-medium">{String(item ?? "—")}</dd></div>)}</dl> : <p className="text-sm text-slate-500">Related record changed</p>}</div>;
}

function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
