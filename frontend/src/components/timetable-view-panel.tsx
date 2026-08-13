"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SectionTimetableGrid } from "@/components/section-timetable-grid";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { timetableApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { SearchableSelect } from "@/components/searchable-select";

export type TimetableViewType = "section" | "faculty" | "classroom" | "laboratory" | "batch";
export type ViewOption = { id: string; label: string };

const labels: Record<TimetableViewType, string> = {
  section: "Section",
  faculty: "Faculty",
  classroom: "Classroom",
  laboratory: "Laboratory",
  batch: "Student batch",
};

export function TimetableViewPanel({ versionId, viewType, initialResourceId = "", options = [] }: { versionId: string; viewType: TimetableViewType; initialResourceId?: string; options?: ViewOption[] }) {
  const [draftId, setDraftId] = useState(initialResourceId);
  const [resourceId, setResourceId] = useState(initialResourceId);
  useEffect(() => { setDraftId(initialResourceId); setResourceId(initialResourceId); }, [initialResourceId, viewType]);
  const query = useQuery({ queryKey: queryKeys.timetableView(versionId, viewType, resourceId), queryFn: () => timetableApi.viewGrid(versionId, viewType, resourceId), enabled: Boolean(resourceId), retry: false });
  const optionMap = useMemo(() => new Map(options.map((option) => [option.id, option.label])), [options]);
  const label = labels[viewType];
  return <div>
    <div className="mb-4 flex flex-wrap items-end gap-3">
      <div className="min-w-72 flex-1"><SearchableSelect label={label} value={draftId} options={options.map((option) => ({ value: option.id, label: option.label }))} onChange={setDraftId} disabled={!options.length} emptyMessage={`No readable ${label.toLowerCase()} records are available`} /></div>
      <button className="button-secondary" disabled={!draftId || query.isFetching} onClick={() => setResourceId(draftId)}>{query.isFetching ? "Loading…" : `Load ${label.toLowerCase()} view`}</button>
    </div>
    {resourceId && <p className="mb-3 text-xs text-slate-500">Showing {optionMap.get(resourceId) ?? "Selected resource"}</p>}
    {!resourceId ? <EmptyState title={`Select a ${label.toLowerCase()}`} detail={options.length ? `Choose a readable ${label.toLowerCase()} to render the ${viewType} timetable.` : "No readable resources are available for this timetable scope."} /> : query.isLoading ? <LoadingState /> : query.isError ? <ErrorState message={apiErrorMessage(query.error)} retry={() => void query.refetch()} /> : <SectionTimetableGrid grid={query.data!} />}
  </div>;
}
