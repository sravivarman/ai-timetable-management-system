"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { timetableApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/providers/toast-provider";

type WorkflowAction = { label: string; endpoint: string; roles: string[]; requiresReason?: boolean; disabledReason?: string };
const actions: Record<string, WorkflowAction[]> = {
  DRAFT: [{ label: "Submit for review", endpoint: "submit-review", roles: ["Administrator", "Timetable Coordinator"], disabledReason: "Run the solver successfully before submitting for review." }],
  GENERATED: [{ label: "Submit for review", endpoint: "submit-review", roles: ["Administrator", "Timetable Coordinator"] }],
  UNDER_REVIEW: [{ label: "Approve", endpoint: "approve", roles: ["Administrator", "Dean", "Principal"] }, { label: "Return to draft", endpoint: "return-to-draft", roles: ["Administrator", "Timetable Coordinator"], requiresReason: true }],
  APPROVED: [{ label: "Publish", endpoint: "publish", roles: ["Administrator", "Principal"] }, { label: "Return to draft", endpoint: "return-to-draft", roles: ["Administrator", "Timetable Coordinator"], requiresReason: true }],
  PUBLISHED: [{ label: "Archive", endpoint: "archive", roles: ["Administrator"] }],
};

export default function TimetableDetailPage() {
  const { timetableId } = useParams<{ timetableId: string }>();
  const client = useQueryClient();
  const { hasRole } = useAuth();
  const { notify } = useToast();
  const timetable = useQuery({ queryKey: queryKeys.timetable(timetableId), queryFn: () => timetableApi.get(timetableId) });
  const versions = useQuery({ queryKey: queryKeys.versions(timetableId), queryFn: () => timetableApi.versions(timetableId) });
  const history = useQuery({ queryKey: queryKeys.history(timetableId), queryFn: () => timetableApi.history(timetableId) });
  const transition = useMutation({
    mutationFn: async (action: WorkflowAction) => {
      if (!window.confirm(`${action.label}?`)) throw new Error("Action cancelled");
      let body: Record<string, unknown> = {};
      if (action.requiresReason) {
        const reason = window.prompt("Reason for returning this timetable to draft");
        if (!reason?.trim()) throw new Error("Action cancelled");
        body = { reason: reason.trim() };
      }
      return timetableApi.transition(timetableId, action.endpoint, body);
    },
    onSuccess: (_, action) => {
      notify(`${action.label} completed`);
      for (const key of [queryKeys.timetable(timetableId), queryKeys.versions(timetableId), queryKeys.history(timetableId), queryKeys.dashboard]) void client.invalidateQueries({ queryKey: key });
    },
    onError: (error) => { if (!(error instanceof Error && error.message === "Action cancelled")) notify(apiErrorMessage(error), "error"); },
  });
  if (timetable.isLoading) return <LoadingState />;
  if (timetable.isError) return <ErrorState message={apiErrorMessage(timetable.error)} retry={() => void timetable.refetch()} />;
  const item = timetable.data!;
  const isAdministrator = hasRole("Administrator", "System Administrator");
  const permitted = (actions[item.status] ?? []).filter((action) => action.roles.some((role) => role === "Administrator" ? isAdministrator : hasRole(role)));
  const activeVersion = versions.data?.items.find((version) => version.id === item.active_version_id);
  return <>
    <PageHeader title={item.name} description={`Timetable ${item.id}`} actions={<div className="flex flex-wrap gap-2">{permitted.map((action) => <button key={action.endpoint} className="button-primary" title={action.disabledReason} disabled={transition.isPending || Boolean(action.disabledReason)} onClick={() => transition.mutate(action)}>{action.label}</button>)}</div>} />
    {permitted.some((action) => action.disabledReason) && <p className="mb-4 text-sm text-slate-500">{permitted.find((action) => action.disabledReason)?.disabledReason}</p>}
    {item.status === "ARCHIVED" && <div className="mb-4 rounded-xl border border-slate-200 bg-slate-100 p-4 text-sm text-slate-700">Archived timetables are read-only. Historical versions, audit history, quality, and comparisons remain available.</div>}
    {transition.isError && transition.error.message !== "Action cancelled" && <div className="mb-4"><ErrorState message={apiErrorMessage(transition.error)} /></div>}
    <div className="grid gap-5 lg:grid-cols-3">
      <Card title="Metadata"><dl className="space-y-3 text-sm"><Metadata label="Status"><StatusBadge value={item.status} /></Metadata><Metadata label="Scope" value={item.scope_type} /><Metadata label="Academic term ID" value={item.academic_term_id} /><Metadata label="Active version" value={item.active_version_id ?? "None"} /><Metadata label="Active version lock"><StatusBadge value={activeVersion?.is_locked ? "LOCKED" : "UNLOCKED"} /></Metadata><Metadata label="Updated" value={new Date(item.updated_at).toLocaleString()} /></dl></Card>
      <Card title="Versions" className="lg:col-span-2">{versions.isLoading ? <LoadingState /> : versions.isError ? <ErrorState message={apiErrorMessage(versions.error)} /> : versions.data?.items.length ? <div className="divide-y">{versions.data.items.map((version) => <div key={version.id} className="flex items-center justify-between gap-4 py-3"><div><p className="font-medium">Version {version.version_number} {version.version_name && `· ${version.version_name}`}</p><div className="mt-1 flex gap-2"><StatusBadge value={version.solver_status} />{version.is_active && <StatusBadge value="ACTIVE" />}{version.is_locked && <StatusBadge value="LOCKED" />}</div></div><Link className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700" href={`/timetable-versions/${version.id}`}>Open <ExternalLink className="h-4 w-4" /></Link></div>)}</div> : <EmptyState title="No versions" />}</Card>
      <Card title="Status history" className="lg:col-span-3">{history.isLoading ? <LoadingState /> : history.isError ? <ErrorState message={apiErrorMessage(history.error)} /> : history.data?.length ? <ol className="relative ml-3 border-l border-slate-300 pl-7">{history.data.map((record) => <li key={record.id} className="mb-7"><span className="absolute -left-2 mt-1 h-4 w-4 rounded-full border-2 border-white bg-brand-600" /><div className="flex flex-wrap items-center gap-2"><StatusBadge value={record.from_status} /><span aria-hidden>→</span><StatusBadge value={record.to_status} /><time className="text-xs text-slate-500">{new Date(record.created_at).toLocaleString()}</time></div><p className="mt-2 text-xs text-slate-500">Performed by {record.performed_by}</p>{record.reason && <p className="mt-1 text-sm text-slate-700">{record.reason}</p>}</li>)}</ol> : <EmptyState title="No workflow transitions yet" />}</Card>
    </div>
  </>;
}

function Metadata({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) { return <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 break-all font-medium">{children ?? value}</dd></div>; }
