"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Download, Eye, Plus, RotateCcw, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { SearchableSelect, type SelectOption } from "@/components/searchable-select";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { reportsApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { sectionLabel, sectionTerm } from "@/lib/section-labels";
import type { AcademicTerm, Course, Department, Faculty, Program, ReportDefinition, ReportRequest, ReportSort, SchedulingSlot, Section } from "@/lib/types";
import { useToast } from "@/providers/toast-provider";
import { useAuth } from "@/providers/auth-provider";
import { normalizeEntityLookupParams, normalizeOptionalEntityFilter, normalizeReportFilters } from "@/lib/report-filter-normalization";

const PREFIX = "administrative-";

export function AdministrativeReportBuilder({ initialReportKey }: { initialReportKey: string }) {
  const router = useRouter();
  const { notify } = useToast();
  const { hasRole } = useAuth();
  const isReportViewer = hasRole("REPORT_VIEWER");
  const definitions = useQuery({ queryKey: queryKeys.reportDefinitions, queryFn: reportsApi.definitions, retry: false });
  const [reportKey, setReportKey] = useState(initialReportKey);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [columns, setColumns] = useState<string[]>([]);
  const [sortFields, setSortFields] = useState<ReportSort[]>([]);
  const [page, setPage] = useState(1);
  const configured = useRef("");
  const termDefaulted = useRef(new Set<string>());
  const definition = definitions.data?.find((item) => item.key === reportKey);

  useEffect(() => setReportKey(initialReportKey), [initialReportKey]);
  useEffect(() => {
    if (!definition || configured.current === definition.key) return;
    configured.current = definition.key;
    setColumns(definition.default_columns);
    setSortFields(definition.default_sort);
    setFilters(defaultReportFilters(definition));
    setPage(1);
  }, [definition]);

  const filterOptions = useQuery({ queryKey: queryKeys.report("administrative-filter-options", {}), queryFn: reportsApi.filterOptions, retry: false });
  const lookupFilters = normalizeEntityLookupParams({ academic_term_id: filters.academic_term_id, department_id: filters.department_id, program_id: filters.program_id });
  const programDepartmentId = normalizeOptionalEntityFilter(filters.department_id);
  const facultyDepartmentId = normalizeOptionalEntityFilter(filters.faculty_department_id || filters.department_id);
  const allPrograms = filterOptions.data?.programs ?? [];
  const allSections = filterOptions.data?.sections ?? [];
  const programs = programDepartmentId ? allPrograms.filter((item) => item.department_id === programDepartmentId) : allPrograms;
  const programIds = new Set(allPrograms.filter((item) => !programDepartmentId || item.department_id === programDepartmentId).map((item) => item.id));
  const sections = allSections.filter((item) => (!lookupFilters.academic_term_id || item.academic_term_id === lookupFilters.academic_term_id) && (!lookupFilters.program_id || item.program_id === lookupFilters.program_id) && (!programDepartmentId || programIds.has(item.program_id)));
  const faculty = facultyDepartmentId ? (filterOptions.data?.faculty ?? []).filter((item) => item.department_id === facultyDepartmentId) : filterOptions.data?.faculty ?? [];

  useEffect(() => {
    if (!definition?.filters.some((item) => item.key === "academic_term_id") || filters.academic_term_id || !filterOptions.data || termDefaulted.current.has(definition.key)) return;
    const preferred = filterOptions.data.academic_terms.find((item) => item.is_current) ?? filterOptions.data.academic_terms.find((item) => item.is_active);
    termDefaulted.current.add(definition.key);
    if (preferred) setFilters((current) => ({ ...current, academic_term_id: preferred.id }));
  }, [definition, filters.academic_term_id, filterOptions.data]);

  const request = useMemo<ReportRequest | null>(() => definition && columns.length ? ({ report_key: definition.key, filters: normalizeReportFilters(filters), selected_columns: columns, sort_fields: sortFields, page, page_size: 50 }) : null, [definition, filters, columns, sortFields, page]);
  const configurationSignature = request ? JSON.stringify({ ...request, page: undefined, page_size: undefined }) : "";
  const [previewedSignature, setPreviewedSignature] = useState("");
  const preview = useMutation({ mutationFn: (payload: ReportRequest) => reportsApi.preview(payload), onSuccess: (_, payload) => setPreviewedSignature(JSON.stringify({ ...payload, page: undefined, page_size: undefined })), onError: (error) => notify(apiErrorMessage(error), "error") });
  const [exporting, setExporting] = useState<string>();

  const runPreview = (nextPage = page) => {
    if (!request) return;
    preview.mutate({ ...request, page: nextPage });
  };
  const exportReport = async (format: "xlsx" | "csv" | "docx" | "pdf") => {
    if (!request) return;
    setExporting(format);
    try {
      const result = await reportsApi.export({ ...request, page: 1 }, format);
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = result.filename; anchor.click(); URL.revokeObjectURL(url);
      notify(`${format === "xlsx" ? "Excel" : format === "docx" ? "Word" : format.toUpperCase()} report downloaded.`);
    } catch (error) { notify(apiErrorMessage(error), "error"); }
    finally { setExporting(undefined); }
  };

  if (definitions.isLoading) return <LoadingState label="Loading report definitions" />;
  if (definitions.error) return <ErrorState message={`Failed to load report metadata: ${apiErrorMessage(definitions.error)}`} retry={() => void definitions.refetch()} />;
  if (!definition) return <ErrorState message="Unknown administrative report." />;

  const reportOptions = (definitions.data ?? []).map((item) => ({ value: item.key, label: item.title, description: item.description }));
  const stale = Boolean(preview.data && previewedSignature !== configurationSignature);
  return <>
    <PageHeader title="Administrative Reports" description="Configure one canonical dataset, preview it, then export the same records to Excel, CSV, Word, or PDF." actions={!isReportViewer ? <Link href="/reports?report=section-timetable" className="button-secondary">Operational reports</Link> : undefined} />
    <Card className="mb-5"><SearchableSelect label="Report" value={reportKey} options={reportOptions} onChange={(value) => { setReportKey(value); router.replace(`/reports?report=${PREFIX}${value}`, { scroll: false }); }} /></Card>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.72fr)]">
      <div className="space-y-5">
        <ReportFilters definition={definition} filters={filters} setFilters={(next, changed) => { setFilters(reconcileDependentFilters(next, changed, allPrograms, allSections)); setPage(1); }} options={{ terms: termOptions(filterOptions.data?.academic_terms ?? []), departments: departmentOptions(filterOptions.data?.departments ?? []), programs: programOptions(programs), sections: sectionOptions(sections, filterOptions.data?.academic_terms ?? []), courses: courseOptions(filterOptions.data?.courses ?? []), faculty: facultyOptions(faculty), slots: slotOptions((filterOptions.data?.scheduling_slots ?? []).filter((item)=>!filters.academic_term_id||item.academic_term_id===filters.academic_term_id)) }} loading={{ academic_term_id: filterOptions.isLoading, department_id: filterOptions.isLoading, faculty_department_id: filterOptions.isLoading, program_id: filterOptions.isLoading, section_id: filterOptions.isLoading, course_id: filterOptions.isLoading, faculty_id: filterOptions.isLoading, scheduling_slot_id: filterOptions.isLoading }} errors={{ academic_term_id: filterOptions.error, department_id: filterOptions.error, faculty_department_id: filterOptions.error, program_id: filterOptions.error, section_id: filterOptions.error, course_id: filterOptions.error, faculty_id: filterOptions.error, scheduling_slot_id: filterOptions.error }} />
        <ColumnPicker definition={definition} selected={columns} onChange={(value) => { setColumns(value); setPage(1); }} />
        <SortEditor definition={definition} value={sortFields} onChange={setSortFields} />
      </div>
      <div className="space-y-5">
        <Card title="Preview & Export">
          {columns.length > 8 && <p role="status" className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">This report contains many columns. Word and PDF will use landscape, compact formatting.</p>}
          {!columns.length && <p role="alert" className="mb-3 text-sm text-red-700">Select at least one report column.</p>}
          {stale && <p className="mb-3 text-sm text-amber-700">Configuration changed. Refresh Preview to see the latest selection.</p>}
          <button className="button-primary w-full gap-2" disabled={!request || preview.isPending} onClick={() => runPreview(1)}><Eye className="h-4 w-4" />{preview.data ? "Refresh Preview" : "Preview Report"}</button>
          <div className="mt-3 grid grid-cols-2 gap-2">{definition.supported_formats.map((format) => <button key={format} aria-label={`Export ${formatName(format)}`} className="button-secondary gap-2" disabled={!request || Boolean(exporting)} onClick={() => void exportReport(format)}><Download className="h-4 w-4" />{exporting === format ? "Exporting…" : formatName(format)}</button>)}</div>
        </Card>
        {preview.isPending ? <Card><LoadingState label="Generating report preview" /></Card> : preview.data ? <Preview result={preview.data} stale={stale} onPage={(next) => { setPage(next); runPreview(next); }} /> : <Card><EmptyState title="Preview not generated" detail="Choose filters, columns, and sorting, then select Preview Report." /></Card>}
      </div>
    </div>
  </>;
}

type OptionCollection = { terms: SelectOption[]; departments: SelectOption[]; programs: SelectOption[]; sections: SelectOption[]; courses: SelectOption[]; faculty: SelectOption[]; slots: SelectOption[] };

function ReportFilters({ definition, filters, setFilters, options, loading, errors }: { definition: ReportDefinition; filters: Record<string, string>; setFilters(value: Record<string, string>, changed: string): void; options: OptionCollection; loading: Record<string, boolean | undefined>; errors: Record<string, unknown> }) {
  const entityOptions: Record<string, SelectOption[]> = { academic_term_id: options.terms, department_id: options.departments, faculty_department_id: options.departments, program_id: options.programs, section_id: options.sections, course_id: options.courses, faculty_id: options.faculty, scheduling_slot_id: options.slots };
  return <Card title="Filters"><div className="grid gap-4 md:grid-cols-2">{definition.filters.map((filter) => filter.control === "entity" ? <SearchableSelect key={filter.key} label={filter.label} value={filters[filter.key] ?? ""} options={[{ value: "", label: "All" }, ...(entityOptions[filter.key] ?? [])]} onChange={(value) => setFilters({ ...filters, [filter.key]: value }, filter.key)} loading={Boolean(loading[filter.key])} error={errors[filter.key] ? apiErrorMessage(errors[filter.key]) : undefined} emptyMessage={`No ${filter.label.toLowerCase()} options available`} /> : <label key={filter.key}><span className="label">{filter.label}</span><select aria-label={filter.label} className="field" value={filters[filter.key] ?? ""} onChange={(event) => setFilters({ ...filters, [filter.key]: event.target.value }, filter.key)}>{!filter.options.includes("ALL") && <option value="">All</option>}{filter.options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}</select></label>)}</div><button className="button-secondary mt-4 gap-2" onClick={() => setFilters(defaultReportFilters(definition), "clear")}><X className="h-4 w-4" />Clear Filters</button></Card>;
}

function ColumnPicker({ definition, selected, onChange }: { definition: ReportDefinition; selected: string[]; onChange(value: string[]): void }) {
  const groups = Map.groupBy(definition.columns, (column) => column.group);
  const move = (index: number, direction: -1 | 1) => { const next = [...selected]; const target = index + direction; if (target < 0 || target >= next.length) return; [next[index], next[target]] = [next[target], next[index]]; onChange(next); };
  return <Card title="Columns"><div className="mb-4 flex flex-wrap gap-2"><button className="button-secondary" onClick={() => onChange(definition.columns.map((item) => item.key))}>Select All</button><button className="button-secondary" onClick={() => onChange([])}>Clear All</button><button className="button-secondary gap-2" onClick={() => onChange(definition.default_columns)}><RotateCcw className="h-4 w-4" />Restore Default</button></div><div className="grid gap-4 md:grid-cols-2">{Array.from(groups.entries()).map(([group, groupColumns]) => <fieldset key={group} className="rounded-lg border p-3"><legend className="px-1 text-sm font-semibold">{group}</legend><div className="space-y-2">{groupColumns.map((column) => <label key={column.key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.includes(column.key)} onChange={(event) => onChange(event.target.checked ? [...selected, column.key] : selected.filter((item) => item !== column.key))} />{column.label}</label>)}</div></fieldset>)}</div><h3 className="mb-2 mt-5 text-sm font-semibold">Selected Columns / Order</h3><ol className="space-y-2">{selected.map((key, index) => { const column = definition.columns.find((item) => item.key === key); return <li key={key} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"><span>{index + 1}. {column?.label}</span><span className="flex"><button aria-label={`Move ${column?.label} up`} className="rounded p-1 hover:bg-slate-100" disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp className="h-4 w-4" /></button><button aria-label={`Move ${column?.label} down`} className="rounded p-1 hover:bg-slate-100" disabled={index === selected.length - 1} onClick={() => move(index, 1)}><ArrowDown className="h-4 w-4" /></button></span></li>; })}</ol></Card>;
}

function SortEditor({ definition, value, onChange }: { definition: ReportDefinition; value: ReportSort[]; onChange(value: ReportSort[]): void }) {
  const sortable = definition.columns.filter((item) => item.sortable);
  const move = (index: number, direction: -1 | 1) => { const next = [...value]; const target = index + direction; if (target < 0 || target >= next.length) return; [next[index], next[target]] = [next[target], next[index]]; onChange(next); };
  return <Card title="Sorting"><div className="space-y-2">{value.map((sort, index) => <div key={`${sort.key}:${index}`} className="grid grid-cols-[1fr_130px_auto] gap-2"><select aria-label={`Sort field ${index + 1}`} className="field" value={sort.key} onChange={(event) => onChange(value.map((item, itemIndex) => itemIndex === index ? { ...item, key: event.target.value } : item))}>{sortable.map((column) => <option key={column.key} value={column.key}>{column.label}</option>)}</select><select aria-label={`Sort direction ${index + 1}`} className="field" value={sort.direction} onChange={(event) => onChange(value.map((item, itemIndex) => itemIndex === index ? { ...item, direction: event.target.value as "asc" | "desc" } : item))}><option value="asc">Ascending</option><option value="desc">Descending</option></select><span className="flex items-center"><button aria-label={`Move sort ${index + 1} up`} className="p-1" disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp className="h-4 w-4" /></button><button aria-label={`Move sort ${index + 1} down`} className="p-1" disabled={index === value.length - 1} onClick={() => move(index, 1)}><ArrowDown className="h-4 w-4" /></button><button aria-label={`Remove sort ${index + 1}`} className="p-1" onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}><X className="h-4 w-4" /></button></span></div>)}</div><div className="mt-3 flex gap-2"><button className="button-secondary gap-2" disabled={value.length >= sortable.length} onClick={() => { const next = sortable.find((column) => !value.some((item) => item.key === column.key)); if (next) onChange([...value, { key: next.key, direction: "asc" }]); }}><Plus className="h-4 w-4" />Add Sort</button><button className="button-secondary" onClick={() => onChange(definition.default_sort)}>Reset Sorting</button></div></Card>;
}

function Preview({ result, stale, onPage }: { result: Awaited<ReturnType<typeof reportsApi.preview>>; stale: boolean; onPage(page: number): void }) {
  return <Card title={result.title}><div className="mb-3 flex flex-wrap gap-2 text-xs text-slate-600">{result.filter_summary.length ? result.filter_summary.map((item) => <span key={item} className="rounded-full bg-slate-100 px-2 py-1">{item}</span>) : <span>No filters</span>}</div><p className="mb-3 text-sm font-medium">{result.total} record{result.total === 1 ? "" : "s"}{stale ? " · Preview is stale" : ""}</p>{!result.rows.length ? <EmptyState title="No records found for the selected filters." /> : <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 dark:bg-slate-800"><tr>{result.columns.map((column) => <th key={column.key} className="whitespace-nowrap px-3 py-2">{column.label}</th>)}</tr></thead><tbody className="divide-y">{result.rows.map((row, index) => <tr key={index}>{result.columns.map((column) => <td key={column.key} className="px-3 py-2 align-top">{display(row[column.key])}</td>)}</tr>)}</tbody></table></div>}<div className="mt-4 flex items-center justify-between"><button className="button-secondary" disabled={result.page <= 1} onClick={() => onPage(result.page - 1)}>Previous</button><span className="text-sm">Page {result.page} of {Math.max(result.pages, 1)}</span><button className="button-secondary" disabled={result.page >= result.pages} onClick={() => onPage(result.page + 1)}>Next</button></div></Card>;
}

function display(value: unknown) { return value === null || value === undefined || value === "" ? "—" : String(value); }
function defaultReportFilters(definition: ReportDefinition): Record<string, string> { return definition.filters.some((item) => item.key === "status" && item.options.includes("ACTIVE")) ? { status: "ACTIVE" } : {}; }
export function reconcileDependentFilters(filters: Record<string, string>, changed: string, programs: Program[], sections: Section[]) {
  const next = { ...filters };
  const selectedProgram = programs.find((item) => item.id === next.program_id);
  const selectedSection = sections.find((item) => item.id === next.section_id);
  if (changed === "department_id" && next.department_id) {
    if (next.program_id && (!selectedProgram || selectedProgram.department_id !== next.department_id)) delete next.program_id;
    const sectionProgram = programs.find((item) => item.id === selectedSection?.program_id);
    if (next.section_id && (!selectedSection || !sectionProgram || sectionProgram.department_id !== next.department_id)) delete next.section_id;
  }
  if (changed === "program_id" && next.program_id && (!selectedSection || selectedSection.program_id !== next.program_id)) delete next.section_id;
  if (changed === "academic_term_id" && next.academic_term_id && (!selectedSection || selectedSection.academic_term_id !== next.academic_term_id)) delete next.section_id;
  return next;
}
function formatName(format: string) { return format === "xlsx" ? "Excel" : format === "docx" ? "Word" : format.toUpperCase(); }
function termOptions(items: AcademicTerm[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.academic_year} • ${item.term_name}`, description: item.is_current ? "Current" : item.is_active ? "Active" : "Historical" })); }
function departmentOptions(items: Department[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.department_code} • ${item.department_name}` })); }
function programOptions(items: Program[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.program_code} • ${item.program_name}` })); }
function sectionOptions(items: Section[], terms: AcademicTerm[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: sectionLabel(item, sectionTerm(item, terms)) })); }
function courseOptions(items: Course[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.course_code} • ${item.course_name}`, description: item.course_type })); }
function facultyOptions(items: Faculty[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.faculty_code} • ${item.full_name}`, description: item.designation })); }
function slotOptions(items: SchedulingSlot[]): SelectOption[] { return items.map((item) => ({ value: item.id, label: `${item.slot_code} • ${item.slot_name}`, description: `${item.start_date} → ${item.end_date}` })); }
