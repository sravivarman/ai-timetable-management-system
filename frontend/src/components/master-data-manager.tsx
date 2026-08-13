"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { BulkImportWizard } from "@/components/bulk-import-wizard";
import { LaboratoryAvailabilityManager } from "@/components/laboratory-availability-manager";
import { ResourceAvailabilityManager } from "@/components/resource-availability-manager";
import { MasterDataTable } from "@/components/master-data-table";
import { MasterRecordForm } from "@/components/master-record-form";
import { RotationMatrixManager } from "@/components/rotation-matrix-manager";
import { SearchableSelect } from "@/components/searchable-select";
import { Card, EmptyState, ErrorState, LoadingState, Modal, PageHeader } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";
import { apiErrorMessage } from "@/lib/api-client";
import { masterDataApi, type MasterRecord } from "@/lib/master-data-api";
import type { Lookup, MasterConfig } from "@/lib/master-data-config";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/providers/toast-provider";
import { readableRecordLabel, safeReadable } from "@/lib/readable-labels";
import { queryKeys } from "@/lib/query-keys";
import { businessExportLookupEndpoints, serializeMasterDataExport } from "@/lib/master-data-export";
import { laboratoryAssignmentPresentation } from "@/lib/course-offering-laboratories";
import type { Page } from "@/lib/types";

type Editor = { mode: "create" | "edit" | "duplicate" | "bulk"; row?: MasterRecord } | null;
export function MasterDataManager({ config, module, variant }: { config: MasterConfig; module: string; variant?: string | null }) {
  const urlSearch = useSearchParams();
  const { user, hasRole } = useAuth(); const isAdministrator = hasRole("Administrator", "System Administrator"); const canManage = isAdministrator || Boolean(user?.roles.some((role) => role.permissions?.some((permission) => permission.resource === config.permission && permission.action === "manage"))); const client = useQueryClient(); const { notify } = useToast();
  const canManageAvailability = (resource: string) => isAdministrator || Boolean(user?.roles.some((role) => role.permissions?.some((permission) => permission.resource === resource && permission.action === "manage")));
  const [page, setPage] = useState(1); const [pageSize, setPageSize] = useState(20); const [search, setSearch] = useState(() => urlSearch.get("search") ?? ""); const [status, setStatus] = useState<"all" | "active" | "inactive">("all"); const [sortKey, setSortKey] = useState(config.columns[0]?.key ?? "id"); const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc"); const [selected, setSelected] = useState<Set<string>>(new Set()); const [editor, setEditor] = useState<Editor>(null); const [details, setDetails] = useState<MasterRecord | null>(null); const [importing, setImporting] = useState(false); const [generating, setGenerating] = useState(false); const searchRef = useRef<HTMLInputElement>(null);
  const [fieldFilters, setFieldFilters] = useState<Record<string, string>>({});
  const filterFields = useMemo(() => config.fields.filter((field) => field.lookup || field.type === "select" || field.type === "boolean").filter((field) => !["is_active", "is_current"].includes(field.name) && !(config.slug === "course-offerings" && field.name === "laboratory_selection_mode")).slice(0, 4), [config]);
  const params = { page, page_size: pageSize, search: search || undefined, is_active: status === "all" ? undefined : status === "active", ...Object.fromEntries(Object.entries(fieldFilters).filter(([, value]) => value !== "")) };
  const rootKey = ["master-data", config.slug] as const; const query = useQuery({ queryKey: [...rootKey, params], queryFn: () => masterDataApi.list(config, params), retry: false });
  const visibleColumns = useMemo(() => config.columns
    .filter((column) => column.key !== "user_id" || isAdministrator)
    .map((column) => config.slug === "courses" && column.key === "weekly_periods" ? { ...column, label: "Weekly Periods" } : config.slug === "course-offerings" && column.key === "weekly_periods_override" ? { ...column, label: "Weekly Periods Override" } : column), [config, isAdministrator]);
  const visibleConfig = useMemo(() => ({ ...config, columns: visibleColumns }), [config, visibleColumns]);
  const lookupDefinitions = useMemo(() => uniqueLookups(visibleConfig), [visibleConfig]);
  const lookupQueries = useQueries({ queries: lookupDefinitions.map((source) => ({ queryKey: ["master-lookup", source.endpoint], queryFn: () => masterDataApi.lookup(source.endpoint), staleTime: 60_000, retry: false })) });
  const lookupRecords: Record<string, MasterRecord[]> = Object.fromEntries(lookupDefinitions.map((source, index) => [source.endpoint, lookupQueries[index].data ?? []]));
  const lookupLabels: Record<string, Map<string, string>> = Object.fromEntries(lookupDefinitions.map((source, index) => [source.endpoint, new Map<string, string>((lookupQueries[index].data ?? []).map((row: MasterRecord) => [String(row[source.valueKey ?? "id"]), source.labelKeys.map((key) => row[key]).filter(Boolean).join(" · ") || readableRecordLabel(source.endpoint, row)]))]));
  const rows = useMemo(() => [...(query.data?.items ?? [])].filter((row) => rowMatches(row, search, config, lookupLabels) && Object.entries(fieldFilters).every(([key, value]) => !value || String(row[key] ?? "") === value)).sort((a, b) => compare(a[sortKey], b[sortKey], sortDirection)), [query.data, search, config, lookupLabels, fieldFilters, sortKey, sortDirection]);
  const presentedRows = useMemo(() => {
    if (config.slug !== "course-offerings") return rows;
    const decorated = rows.map((row) => {
      const course = (lookupRecords["/courses"] ?? []).find((item) => item.id === String(row.course_id));
      const laboratoryLabel = row.laboratory_override_id ? lookupLabels["/laboratories"]?.get(String(row.laboratory_override_id)) : undefined;
      const presentation = laboratoryAssignmentPresentation(row, course, laboratoryLabel);
      return { ...row, laboratory_assignment_display: presentation.assignment, laboratory_selection_display: presentation.laboratory };
    });
    return ["laboratory_assignment_display", "laboratory_selection_display"].includes(sortKey)
      ? decorated.sort((a, b) => compare((a as MasterRecord)[sortKey], (b as MasterRecord)[sortKey], sortDirection))
      : decorated;
  }, [config.slug, rows, lookupRecords, lookupLabels, sortKey, sortDirection]);
  const invalidate = () => client.invalidateQueries({ queryKey: rootKey });
  const save = useMutation({ mutationFn: async (payload: Record<string, unknown>) => { if (editor?.mode === "edit" && editor.row) return masterDataApi.update(config, editor.row.id, payload); if (editor?.mode === "bulk") { for (const row of rows.filter((item) => selected.has(item.id))) await masterDataApi.update(config, row.id, { ...editable(row, config), ...payload }); return null; } return masterDataApi.create(config, payload); }, onSuccess: () => { notify(editor?.mode === "bulk" ? `${selected.size} records updated.` : `${config.singular} saved.`); setEditor(null); setSelected(new Set()); void invalidate(); }, onError: (error) => notify(apiErrorMessage(error), "error") });
  const remove = useMutation({ mutationFn: async (records: MasterRecord[]) => { for (const row of records) await masterDataApi.remove(config, row.id); }, onSuccess: (_, records) => { notify(`${records.length} ${records.length === 1 ? "record" : "records"} deleted.`); setSelected(new Set()); void invalidate(); }, onError: (error) => notify(apiErrorMessage(error), "error") });
  const restore = useMutation({ mutationFn: (row: MasterRecord) => masterDataApi.restore(config, row.id), onSuccess: () => { notify(`${config.singular} restored.`); void invalidate(); }, onError: (error) => notify(apiErrorMessage(error), "error") });
  const activate = useMutation({
    mutationFn: async (row: MasterRecord) => {
      const activated = await masterDataApi.update(config, row.id, { is_active: true, is_current: true });
      for (const previous of rows.filter((item) => item.id !== row.id && item.is_current === true)) {
        await masterDataApi.update(config, previous.id, { is_current: false });
      }
      return activated;
    },
    onSuccess: async (activated) => {
      client.setQueriesData<Page<MasterRecord>>({ queryKey: rootKey }, (current) => current ? { ...current, items: current.items.map((item) => ({ ...item, is_current: item.id === activated.id })) } : current);
      notify("Academic term activated.");
      await Promise.all([
        client.invalidateQueries({ queryKey: rootKey }),
        client.invalidateQueries({ queryKey: queryKeys.academicTerms }),
        client.invalidateQueries({ queryKey: queryKeys.dashboard }),
        client.invalidateQueries({ queryKey: ["report"] }),
        client.invalidateQueries({ queryKey: ["global-search"] }),
      ]);
    },
    onError: (error) => notify(apiErrorMessage(error), "error"),
  });
  useEffect(() => { const shortcut = (event: KeyboardEvent) => { if (event.key === "/" && !isInput(event.target)) { event.preventDefault(); searchRef.current?.focus(); } if (event.key.toLowerCase() === "n" && event.altKey && canManage) { event.preventDefault(); setEditor({ mode: "create" }); } }; document.addEventListener("keydown", shortcut); return () => document.removeEventListener("keydown", shortcut); }, [canManage]);
  const bulkDelete = () => { const records = rows.filter((row) => selected.has(row.id)); if (records.length && window.confirm(`Delete ${records.length} selected records? Historical rows will be soft-deleted where supported.`)) remove.mutate(records); };
  const exportRows = async (data: MasterRecord[]) => {
    const endpoints = businessExportLookupEndpoints(config);
    const records = await Promise.all(endpoints.map((endpoint) => masterDataApi.lookup(endpoint, true)));
    return serializeMasterDataExport(config, data, Object.fromEntries(endpoints.map((endpoint, index) => [endpoint, records[index]])));
  };
  const exportAll = async () => { try { const data = await exportRows(await masterDataApi.all(config)); downloadCsv(`${config.slug}-all`, data); notify(`${data.length} records exported.`); } catch (error) { notify(apiErrorMessage(error), "error"); } };
  const exportFiltered = async () => { try { const data = await masterDataApi.all(config, { search: search || undefined, is_active: status === "all" ? undefined : status === "active", ...Object.fromEntries(Object.entries(fieldFilters).filter(([, value]) => value !== "")) }); const filtered = data.filter((row) => rowMatches(row, search, config, lookupLabels) && Object.entries(fieldFilters).every(([key, value]) => !value || String(row[key] ?? "") === value)).sort((a, b) => compare(a[sortKey], b[sortKey], sortDirection)); const exported = await exportRows(filtered); downloadCsv(`${config.slug}-filtered`, exported); notify(`${exported.length} filtered records exported.`); } catch (error) { notify(apiErrorMessage(error), "error"); } };
  return <><PageHeader title={config.label} description={config.description} actions={<div className="flex flex-wrap gap-2"><Link className="button-secondary" href="/master-data">Master dashboard</Link><button className="button-secondary gap-2" disabled={query.isFetching} onClick={() => void query.refetch()}><RefreshCw className={`h-4 w-4 ${query.isFetching ? "animate-spin" : ""}`} />Refresh</button>{canManage && <button className="button-primary gap-2" onClick={() => setEditor({ mode: "create" })}><Plus className="h-4 w-4" />Add</button>}</div>} />
    {(module === "faculty-allocations" || module === "laboratory-configuration") && <VariantTabs module={module} variant={variant} />}
    {config.limitation && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">{config.limitation}</div>}
    <Card><div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5"><label className="xl:col-span-2"><span className="label">Search</span><input ref={searchRef} className="field" aria-label={`Search ${config.label}`} placeholder={`Search ${config.searchKeys.map((key) => key.replaceAll("_", " ")).join(", ")}…`} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /></label><label><span className="label">Status</span><select className="field" aria-label="Status filter" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="all">All records</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label><label><span className="label">Page size</span><select className="field" aria-label="Page size" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>{[10,20,50,100].map((size) => <option key={size}>{size}</option>)}</select></label><div className="flex items-end"><button className="button-secondary w-full" onClick={() => { setSearch(""); setStatus("all"); setFieldFilters({}); setSelected(new Set()); setPage(1); }}>Clear filters</button></div></div>
      {filterFields.length > 0 && <details className="mb-4 rounded-lg border p-3 dark:border-slate-700"><summary className="cursor-pointer text-sm font-semibold">Module filters</summary><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{filterFields.map((field) => <label key={field.name}><span className="label">{field.label}</span><select className="field" aria-label={`Filter by ${field.label}`} value={fieldFilters[field.name] ?? ""} onChange={(event) => { setFieldFilters((current) => ({ ...current, [field.name]: event.target.value })); setPage(1); }}><option value="">All</option>{field.lookup ? (lookupRecords[field.lookup.endpoint] ?? []).map((row) => <option key={row.id} value={String(row[field.lookup!.valueKey ?? "id"])}>{field.lookup!.labelKeys.map((key) => row[key]).filter(Boolean).join(" · ")}</option>) : field.type === "boolean" ? <><option value="true">Yes</option><option value="false">No</option></> : field.options?.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}</select></label>)}</div></details>}
      <div className="mb-4 flex flex-wrap items-center gap-2 print:hidden"><span className="rounded-full bg-slate-100 px-3 py-1 text-xs dark:bg-slate-800">{query.data?.total ?? 0} records</span>{search && <span className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700">Search: {search}</span>}{status !== "all" && <span className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700">{status}</span>}{Object.entries(fieldFilters).filter(([, value]) => value).map(([key, value]) => <span key={key} className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700">{config.fields.find((field) => field.name === key)?.label}: {lookupLabels[config.fields.find((field) => field.name === key)?.lookup?.endpoint ?? ""]?.get(value) ?? safeReadable(value)}</span>)}<span className="ml-auto text-xs text-slate-500">Shortcut: / search · Alt+N add</span></div>
      {lookupQueries.some((item) => item.isError) && <div role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">Some relationship labels could not be loaded. Create and edit actions may be limited by your permissions.</div>}
      <div className="mb-4 flex flex-wrap gap-2 print:hidden"><button className="button-secondary gap-2" disabled={!rows.length} onClick={() => void exportFiltered()}><Download className="h-4 w-4" />Export current filter</button><button className="button-secondary" onClick={() => void exportAll()}>Export entire dataset</button>{canManage && <><button className="button-secondary gap-2" onClick={() => setImporting(true)}><FileUp className="h-4 w-4" />Import CSV</button><button className="button-secondary" disabled={!selected.size} onClick={() => setEditor({ mode: "bulk" })}>Bulk update ({selected.size})</button><button className="button-secondary gap-2 text-red-700" disabled={!selected.size || remove.isPending} onClick={bulkDelete}><Trash2 className="h-4 w-4" />Bulk delete ({selected.size})</button>{config.supportsGenerate && <button className="button-secondary" onClick={() => setGenerating(true)}>Generate student groups</button>}</>}</div>
      {query.isLoading ? <LoadingState /> : query.isError ? <ErrorState message={apiErrorMessage(query.error)} retry={() => void query.refetch()} /> : !rows.length ? <EmptyState title={`No ${config.label.toLowerCase()} found`} detail={search || status !== "all" ? "Change or clear the filters." : canManage ? "Add the first record or import a CSV file." : "No readable records are available."} /> : <><MasterDataTable rows={presentedRows} columns={visibleColumns} lookups={lookupLabels} selected={selected} onSelection={setSelected} sortKey={sortKey} sortDirection={sortDirection} onSort={(key) => { if (sortKey === key) setSortDirection((current) => current === "asc" ? "desc" : "asc"); else { setSortKey(key); setSortDirection("asc"); } }} canManage={canManage} onView={setDetails} onEdit={(row) => setEditor({ mode: "edit", row })} onDuplicate={(row) => setEditor({ mode: "duplicate", row })} onDelete={(row) => { if (window.confirm(`Delete this ${config.singular.toLowerCase()}?`)) remove.mutate([row]); }} onRestore={(row) => restore.mutate(row)} onActivate={config.slug === "academic-terms" ? (row) => activate.mutate(row) : undefined} /><div className="mt-4 flex items-center justify-between text-sm"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {query.data?.page ?? page} of {Math.max(query.data?.pages ?? 1, 1)}</span><button className="button-secondary" disabled={page >= (query.data?.pages ?? 1)} onClick={() => setPage((value) => value + 1)}>Next</button></div></>}
    </Card>
    {config.slug === "faculty-availability" && <WeeklyConstraintGrid config={config} rows={rows} lookupLabels={lookupLabels} />}
    {(config.slug === "laboratories" || config.slug === "lab-availability-blocks") && <LaboratoryAvailabilityManager canManage={canManageAvailability("laboratory_blocks")} />}
    {config.slug === "classrooms" && <ResourceAvailabilityManager resourceType="CLASSROOM" canManage={canManageAvailability("classrooms")} />}
    {(config.slug === "faculty" || config.slug === "faculty-availability") && <ResourceAvailabilityManager resourceType="FACULTY" canManage={canManageAvailability("faculty_availability")} />}
    {config.slug === "rotations" && <RotationMatrixManager rotations={rows} canManage={canManage} />}
    {editor && <MasterRecordForm config={config} initial={editor.row} lookupRecords={lookupRecords} mode={editor.mode} busy={save.isPending} onClose={() => setEditor(null)} onSubmit={(payload) => save.mutate(payload)} />}
    {details && <DetailsModal config={visibleConfig} row={details} lookups={lookupLabels} onClose={() => setDetails(null)} />}
    {importing && <BulkImportWizard config={config} onClose={() => setImporting(false)} onComplete={() => void invalidate()} />}
    {generating && <GenerateBatches lookupRecords={lookupRecords} busy={save.isPending} onClose={() => setGenerating(false)} onComplete={() => { setGenerating(false); void invalidate(); }} />}
  </>;
}

function VariantTabs({ module, variant }: { module: string; variant?: string | null }) { const tabs = module === "faculty-allocations" ? [["theory","Theory Allocations"],["laboratory","Laboratory Allocations"]] : [["batch-configurations","Student Group Configurations"],["rotations","Rotation Matrix"]]; return <nav className="mb-4 flex flex-wrap gap-2" aria-label={`${module} views`}>{tabs.map(([value, label]) => <Link key={value} className={`rounded-lg px-4 py-2 text-sm font-semibold ${(variant ?? tabs[0][0]) === value ? "bg-brand-600 text-white" : "button-secondary"}`} href={`/master-data/${module}?variant=${value}`}>{label}</Link>)}</nav>; }
function DetailsModal({ config, row, lookups, onClose }: { config: MasterConfig; row: MasterRecord; lookups: Record<string, Map<string, string>>; onClose(): void }) { return <Modal title={`${config.singular} details`} onClose={onClose}><dl className="grid gap-3 sm:grid-cols-2">{config.columns.map((column) => <div key={column.key} className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800"><dt className="text-xs text-slate-500">{column.label}</dt><dd className="mt-1 break-all text-sm font-semibold">{column.lookup ? lookups[column.lookup.endpoint]?.get(String(row[column.key])) ?? String(row[column.key] ?? column.fallback ?? "—") : Array.isArray(row[column.key]) ? (row[column.key] as unknown[]).join(", ") : String(row[column.key] ?? column.fallback ?? "—")}</dd></div>)}</dl></Modal>; }
function GenerateBatches({ lookupRecords, busy, onClose, onComplete }: { lookupRecords: Record<string, MasterRecord[]>; busy: boolean; onClose(): void; onComplete(): void }) {
  const [sectionId, setSectionId] = useState("");
  const [count, setCount] = useState("1");
  const [namingPattern, setNamingPattern] = useState("{section}{sequence}");
  const [overwrite, setOverwrite] = useState(false);
  const [error, setError] = useState("");
  const section = (lookupRecords["/sections"] ?? []).find((row) => row.id === sectionId);
  const groupCount = Number(count);
  const strength = Number(section?.student_strength ?? 0);
  const validCount = Number.isInteger(groupCount) && groupCount >= 1 && (!strength || groupCount <= strength);
  const preview = validCount && section ? Array.from({ length: groupCount }, (_, index) => {
    const sequence = index + 1;
    const base = Math.floor(strength / groupCount);
    const size = base + (sequence <= strength % groupCount ? 1 : 0);
    const name = namingPattern
      .replaceAll("{section}", String(section.section_name ?? "GROUP"))
      .replaceAll("{section_code}", String(section.section_code ?? "GROUP"))
      .replaceAll("{sequence}", String(sequence))
      .toUpperCase();
    return { name, size };
  }) : [];
  const generate = async () => {
    try {
      setError("");
      await masterDataApi.generateBatches({ section_id: sectionId, number_of_groups: groupCount, naming_pattern: namingPattern, overwrite });
      onComplete();
    } catch (reason) { setError(apiErrorMessage(reason)); }
  };
  return <Modal title="Generate student groups" onClose={onClose} footer={<><button className="button-secondary" onClick={onClose}>Cancel</button><button className="button-primary" disabled={!sectionId || !validCount || !namingPattern.trim() || busy} onClick={() => void generate()}>Generate</button></>}>
    <div className="space-y-4">
      <SearchableSelect label="Section" value={sectionId} options={(lookupRecords["/sections"] ?? []).map((row) => ({ value: row.id, label: readableRecordLabel("/sections", row) }))} onChange={setSectionId} />
      <label><span className="label">Number of Student Groups</span><input className="field" aria-label="Number of Student Groups" type="number" min={1} max={strength || undefined} step={1} value={count} onChange={(event) => setCount(event.target.value)} /></label>
      <label><span className="label">Naming pattern</span><input className="field" aria-label="Group naming pattern" value={namingPattern} onChange={(event) => setNamingPattern(event.target.value)} /><span className="mt-1 block text-xs text-slate-500">Use {"{section}"}, {"{section_code}"}, and {"{sequence}"}. A single group may use a literal name such as FULL.</span></label>
      {section && !validCount && <p role="alert" className="text-sm text-red-700">Enter a whole number from 1 to the section strength ({strength}).</p>}
      {preview.length > 0 && <div className="rounded-lg border p-3 dark:border-slate-700"><p className="mb-2 text-sm font-semibold">Generated groups</p><div className="max-h-48 space-y-1 overflow-y-auto" aria-label="Generated group preview">{preview.map((group, index) => <div className="flex justify-between rounded bg-slate-50 px-3 py-1 text-sm dark:bg-slate-800" key={`${group.name}-${index}`}><span>{group.name}</span><span className="text-slate-500">{group.size} students</span></div>)}</div></div>}
      <label className="flex items-center gap-2"><input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />Replace existing active student groups</label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </div>
  </Modal>;
}
function WeeklyConstraintGrid({ config, rows, lookupLabels }: { config: MasterConfig; rows: MasterRecord[]; lookupLabels: Record<string, Map<string, string>> }) { const days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]; return <Card title="Weekly visualization" className="mt-5"><div className="overflow-x-auto"><table className="w-full min-w-[800px] text-center text-xs"><thead><tr><th className="p-2 text-left">Day</th>{[1,2,3,4,5,6,7].map((period) => <th className="p-2" key={period}>P{period}</th>)}</tr></thead><tbody>{days.map((day) => <tr key={day}><th className="border p-2 text-left dark:border-slate-700">{day}</th>{[1,2,3,4,5,6,7].map((period) => { const matches = rows.filter((row) => config.slug === "faculty-availability" ? row.day_of_week === day && Number(row.period_number) === period : lookupLabels["/working-days"]?.get(String(row.working_day_id)) === day && Number(row.period_number) === period); return <td className={`border p-2 dark:border-slate-700 ${matches.length ? "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-200" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30"}`} key={period}>{matches.length ? matches.map((row) => String(row.availability_type ?? "Blocked")).join(", ") : "Available"}</td>; })}</tr>)}</tbody></table></div></Card>; }
function uniqueLookups(config: MasterConfig): Lookup[] { const values = [...config.columns.map((column) => column.lookup), ...config.fields.map((field) => field.lookup)].filter((value): value is Lookup => Boolean(value)); return Array.from(new Map(values.map((value) => [value.endpoint, value])).values()); }
function compare(left: unknown, right: unknown, direction: "asc" | "desc") { const result = String(left ?? "").localeCompare(String(right ?? ""), undefined, { numeric: true }); return direction === "asc" ? result : -result; }
function editable(row: MasterRecord, config: MasterConfig) { return Object.fromEntries(config.fields.filter((field) => row[field.name] !== undefined).map((field) => [field.name, row[field.name]])); }
function isInput(target: EventTarget | null) { return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement; }
function rowMatches(row: MasterRecord, search: string, config: MasterConfig, lookups: Record<string, Map<string, string>>) { if (!search) return true; const needle = search.toLowerCase(); if (config.searchKeys.some((key) => String(row[key] ?? "").toLowerCase().includes(needle))) return true; return config.columns.some((column) => column.lookup && (lookups[column.lookup.endpoint]?.get(String(row[column.key])) ?? "").toLowerCase().includes(needle)); }
