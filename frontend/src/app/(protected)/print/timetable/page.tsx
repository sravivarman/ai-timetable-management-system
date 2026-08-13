"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Suspense } from "react";
import { ReportTools } from "@/components/report-tools";
import { LaboratoryAvailabilityManager } from "@/components/laboratory-availability-manager";
import { ResourceAvailabilityManager } from "@/components/resource-availability-manager";
import { SectionTimetableGrid } from "@/components/section-timetable-grid";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { timetableApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

const views = ["section", "faculty", "classroom", "laboratory", "batch"] as const;
export default function PrintTimetablePage() { return <Suspense fallback={<LoadingState />}><PrintTimetable /></Suspense>; }
function PrintTimetable() {
  const params = useSearchParams(); const versionId = params.get("version_id") ?? ""; const resourceId = params.get("resource_id") ?? ""; const academicTermId = params.get("academic_term_id") ?? ""; const readableLabel = params.get("label") ?? "Selected resource"; const raw = params.get("view_type") ?? "section"; const viewType = views.includes(raw as typeof views[number]) ? raw as typeof views[number] : "section";
  const query = useQuery({ queryKey: queryKeys.timetableView(versionId, viewType, resourceId), queryFn: () => timetableApi.viewGrid(versionId, viewType, resourceId), enabled: Boolean(versionId && resourceId), retry: false });
  return <>{!versionId || !resourceId ? <EmptyState title="Missing print parameters" detail="Open this page from a timetable report." /> : query.isLoading ? <LoadingState /> : query.isError ? <ErrorState message={apiErrorMessage(query.error)} retry={() => void query.refetch()} /> : <><PageHeader title={`${viewType[0].toUpperCase()}${viewType.slice(1)} timetable`} description={readableLabel} actions={<ReportTools filename={`${readableLabel}-${viewType}-timetable`} rows={query.data!.days.flatMap((day) => day.entries.map((entry) => ({ ...entry })))} />} /><SectionTimetableGrid grid={query.data!} />{viewType === "laboratory" && academicTermId && <LaboratoryAvailabilityManager initialLaboratoryId={resourceId} initialTermId={academicTermId} occupiedPeriodCount={query.data!.days.reduce((total, day) => total + day.entries.reduce((count, entry) => count + entry.period_numbers.length, 0), 0)} printable />}{viewType === "classroom" && academicTermId && <ResourceAvailabilityManager resourceType="CLASSROOM" initialResourceId={resourceId} initialTermId={academicTermId} occupiedPeriodCount={query.data!.days.reduce((total, day) => total + day.entries.reduce((count, entry) => count + entry.period_numbers.length, 0), 0)} printable />}{viewType === "faculty" && academicTermId && <ResourceAvailabilityManager resourceType="FACULTY" initialResourceId={resourceId} initialTermId={academicTermId} occupiedPeriodCount={query.data!.days.reduce((total, day) => total + day.entries.reduce((count, entry) => count + entry.period_numbers.length, 0), 0)} printable />}</>}</>;
}
