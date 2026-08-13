"use client";

import { useQueries } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/components/ui";
import { parseCsv, type CsvPreview } from "@/lib/csv-import";
import { downloadCsv } from "@/lib/csv";
import { masterDataApi, type MasterRecord } from "@/lib/master-data-api";
import type { MasterConfig } from "@/lib/master-data-config";
import { apiErrorMessage } from "@/lib/api-client";
import {
  baselineStillMatches,
  classifyImportRows,
  importSummary,
  meaningfulDifferences,
  updatePayload,
  type ClassifiedImportRow,
  type ImportRowStatus,
} from "@/lib/csv-import-classification";
import { csvTemplateColumns, findExistingImportRecord, importLookupEndpoints, requiredCsvColumns, resolveCsvImportRow } from "@/lib/csv-import-resolution";
import { resolveLaboratoryAvailabilityCsv } from "@/lib/laboratory-availability-csv";
import { masterConfigs } from "@/lib/master-data-config";

type Stage = "upload" | "preview" | "processing" | "review";
type ReviewFilter = "ALL" | "CREATED" | "CHANGED" | "IDENTICAL" | "INVALID" | "CONFLICT";

export function BulkImportWizard({ config, onClose, onComplete }: { config: MasterConfig; onClose(): void; onComplete(): void }) {
  const [stage, setStage] = useState<Stage>("upload");
  const [preview, setPreview] = useState<CsvPreview>({ headers: [], rows: [], errors: [] });
  const [rows, setRows] = useState<ClassifiedImportRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<ReviewFilter>("ALL");
  const endpoints = useMemo(() => importLookupEndpoints(config), [config]);
  const lookupQueries = useQueries({ queries: endpoints.map((endpoint) => ({ queryKey: ["csv-import-lookup", endpoint], queryFn: () => masterDataApi.lookup(endpoint, true), staleTime: 60_000, retry: false })) });
  const lookupRecords = useMemo(() => Object.fromEntries(endpoints.map((endpoint, index) => [endpoint, lookupQueries[index].data ?? []])), [endpoints, lookupQueries]);
  const requiredMissing = useMemo(() => requiredCsvColumns(config).filter((column) => !preview.headers.includes(column)), [config, preview.headers]);
  const lookupLoading = lookupQueries.some((query) => query.isLoading);
  const lookupErrors = lookupQueries.flatMap((query, index) => query.isError ? [`Could not load ${endpoints[index]} references: ${apiErrorMessage(query.error)}`] : []);
  const blockingProblems = preview.errors.length > 0 || requiredMissing.length > 0 || lookupErrors.length > 0;
  const totals = importSummary(rows);

  useEffect(() => {
    if (stage !== "preview" || lookupLoading || blockingProblems || !preview.rows.length || rows.length) return;
    const resolved = preview.rows.map((row) => resolveCsvImportRow(config, row, lookupRecords));
    setRows(classifyImportRows(config, resolved, lookupRecords));
  }, [blockingProblems, config, lookupLoading, lookupRecords, preview.rows, rows.length, stage]);

  const createNew = async () => {
    if (!totals.new) { setStage("review"); return; }
    setBusy(true); setStage("processing");
    let current: MasterRecord[];
    try { current = await masterDataApi.lookup(config.endpoint, true); }
    catch (error) {
      setRows((value) => value.map((row) => row.status === "NEW" ? { ...row, status: "CONFLICT", messages: [...row.messages, `Current database state could not be verified: ${apiErrorMessage(error)}`] } : row));
      setBusy(false); setStage("review"); return;
    }
    const next = [...rows];
    const creationOrder = next.map((row, index) => ({ row, index })).filter(({ row }) => row.status === "NEW").sort((left, right) => activityDependencyRank(config, left.row) - activityDependencyRank(config, right.row) || left.index - right.index);
    for (const { index } of creationOrder) {
      const row = next[index];
      const match = findExistingImportRecord(config, row.payload, current);
      if (match.error) { next[index] = { ...row, status: "CONFLICT", messages: [...row.messages, match.error] }; continue; }
      if (match.record) {
        const differences = meaningfulDifferences(config, match.record, row.payload, row.source, lookupRecords);
        next[index] = { ...row, status: differences.length ? "CONFLICT" : "NO_CHANGES", existing: match.record, baseline: { ...match.record }, differences, messages: differences.length ? [...row.messages, "A matching record appeared after preview. Review the current database values before updating."] : [...row.messages, "A matching identical record already exists."] };
        continue;
      }
      try {
        const created = await masterDataApi.create(config, row.payload);
        if (config.slug === "laboratories") await importLaboratorySlots(created, row.source, lookupRecords);
        current.push(created);
        next[index] = { ...row, status: "CREATED", existing: created, baseline: { ...created }, messages: [...row.messages, "Created through the normal validated API."] };
      } catch (error) {
        const message = apiErrorMessage(error);
        next[index] = { ...row, status: isConflictMessage(message) ? "CONFLICT" : "INVALID", messages: [...row.messages, message] };
      }
    }
    setRows(next); setBusy(false); setStage("review"); onComplete();
  };

  const updateChanged = async (rowNumber: number) => {
    const index = rows.findIndex((row) => row.rowNumber === rowNumber); const row = rows[index];
    if (!row?.existing || !row.baseline || row.status !== "CHANGED") return;
    setBusy(true);
    try {
      const current = await masterDataApi.get(config, row.existing.id);
      if (!baselineStillMatches(config, row.baseline, current, row.source)) {
        setRows((value) => replaceRow(value, rowNumber, { ...row, status: "CONFLICT", existing: current, differences: meaningfulDifferences(config, current, row.payload, row.source, lookupRecords), messages: [...row.messages, "Record changed since import preview. Preview Existing, Current Database, and Imported values must be reviewed again."] }));
      } else {
        const expected = typeof current.updated_at === "string" ? current.updated_at : undefined;
        let updated = await masterDataApi.update(config, current.id, updatePayload(row), expected);
        const requestedActive = row.payload.is_active;
        const lifecycleBaseline = typeof updated.updated_at === "string" ? updated.updated_at : expected;
        if (requestedActive === false && current.is_active !== false) { await masterDataApi.remove(config, current.id, lifecycleBaseline); updated = { ...updated, is_active: false }; }
        if (requestedActive === true && current.is_active === false) { updated = await masterDataApi.restore(config, current.id, lifecycleBaseline); }
        if (config.slug === "laboratories") await importLaboratorySlots(updated, row.source, lookupRecords, current);
        setRows((value) => replaceRow(value, rowNumber, { ...row, status: "UPDATED", existing: updated, baseline: { ...updated }, differences: [], messages: [...row.messages, "Approved changes were applied through the normal validated API."] }));
        onComplete();
      }
    } catch (error) {
      const message = apiErrorMessage(error);
      setRows((value) => replaceRow(value, rowNumber, { ...row, status: message.toLowerCase().includes("changed since") ? "CONFLICT" : "INVALID", messages: [...row.messages, message] }));
    } finally { setBusy(false); }
  };

  const keepExisting = (rowNumber: number) => setRows((value) => value.map((row) => row.rowNumber === rowNumber && row.status === "CHANGED" ? { ...row, status: "KEPT_EXISTING", differences: [], messages: [...row.messages, "Keep Existing selected; the database was not modified."] } : row));
  const bulkUpdate = async () => {
    const changed = rows.filter((row) => row.status === "CHANGED");
    if (!changed.length || !window.confirm(`${changed.length} existing records will be updated. Continue?`)) return;
    for (const row of changed) await updateChanged(row.rowNumber);
  };
  const bulkKeep = () => setRows((value) => value.map((row) => row.status === "CHANGED" ? { ...row, status: "KEPT_EXISTING", differences: [], messages: [...row.messages, "Keep Existing selected; the database was not modified."] } : row));
  const visibleRows = rows.filter((row) => filter === "ALL" || filter === "CREATED" && row.status === "CREATED" || filter === "CHANGED" && ["CHANGED", "UPDATED", "KEPT_EXISTING"].includes(row.status) || filter === "IDENTICAL" && ["IDENTICAL", "NO_CHANGES"].includes(row.status) || row.status === filter);

  const footer = stage === "upload" ? <button className="button-secondary" onClick={onClose}>Cancel</button>
    : stage === "preview" ? <><button className="button-secondary" onClick={onClose}>Cancel</button><button className="button-primary" disabled={busy || blockingProblems || lookupLoading || !rows.length} onClick={() => void createNew()}>{totals.new ? `Create ${totals.new} New Records` : "Continue to Review"}</button></>
    : stage === "review" ? <button className="button-primary" onClick={onClose}>Done</button> : null;

  return <Modal title={`Import ${config.label} from CSV`} onClose={onClose} wide footer={footer}>
    <ol className="mb-6 grid grid-cols-4 gap-2 text-center text-xs" aria-label="Import progress">{["Upload","Preview","Create New","Review"].map((label, index) => { const active = ["upload","preview","processing","review"][index] === stage; return <li key={label} className={`rounded px-2 py-2 ${active ? "bg-brand-600 text-white" : "bg-slate-100 dark:bg-slate-800"}`}>{label}</li>; })}</ol>
    {stage === "upload" && <UploadStep config={config} lookupLoading={lookupLoading} lookupErrors={lookupErrors} onFile={(value) => { setPreview(value); setRows([]); setStage("preview"); }} />}
    {stage === "preview" && <><ImportProblems errors={[...preview.errors, ...lookupErrors, ...requiredMissing.map((column) => `Missing required column: ${column}`)]} /><p className="mb-3 text-sm">No database writes have occurred. Review the classification, then create only valid NEW records.</p><SummaryCards rows={rows} /><ResolvedPreviewTable rows={rows} /></>}
    {stage === "processing" && <div role="status" className="p-10 text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-brand-200 border-t-brand-600" /><p className="mt-4">Rechecking business keys and creating NEW records through validated APIs…</p></div>}
    {stage === "review" && <><SummaryCards rows={rows} postCreate /><div className="my-4 flex flex-wrap gap-2"><button className="button-secondary" disabled={busy || !rows.some((row) => row.status === "CHANGED")} onClick={() => void bulkUpdate()}>Update All Changed</button><button className="button-secondary" disabled={busy || !rows.some((row) => row.status === "CHANGED")} onClick={bulkKeep}>Keep Existing for All Changed</button>{rows.some((row) => ["INVALID", "CONFLICT"].includes(row.status)) && <button className="button-secondary" disabled={busy} onClick={() => { setPreview({ headers: [], rows: [], errors: [] }); setRows([]); setStage("upload"); }}>Upload Corrected CSV</button>}{(["ALL","CREATED","CHANGED","IDENTICAL","INVALID","CONFLICT"] as ReviewFilter[]).map((value) => <button key={value} className={filter === value ? "button-primary" : "button-secondary"} onClick={() => setFilter(value)}>{value === "CHANGED" ? "Needs Review" : value === "IDENTICAL" ? "No Changes" : title(value)}</button>)}</div><ReviewRows rows={visibleRows} busy={busy} onUpdate={updateChanged} onKeep={keepExisting} /></>}
  </Modal>;
}

function UploadStep({ config, lookupLoading, lookupErrors, onFile }: { config: MasterConfig; lookupLoading: boolean; lookupErrors: string[]; onFile(value: CsvPreview): void }) {
  return <div className="space-y-4"><p className="text-sm text-slate-600 dark:text-slate-300">Upload UTF-8 CSV using institutional business keys. Existing records are never changed without explicit approval, and absent rows are never deleted.</p><p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">Academic terms use <strong>academic_term_code</strong> in the format <code>2026-27 | I-I</code>. UUIDs are resolved internally and are not accepted as the normal import identity.</p><button className="button-secondary" onClick={() => downloadCsv(`${config.slug}-template`, [Object.fromEntries(csvTemplateColumns(config).map((column) => [column, ""]))])}>Download readable-key template</button>{lookupLoading && <p role="status" className="text-sm">Loading reference dictionaries and existing records…</p>}<ImportProblems errors={lookupErrors} /><label className="block rounded-xl border-2 border-dashed p-8 text-center"><span className="block font-semibold">Choose CSV file</span><input aria-label="CSV file" className="mt-4" type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (file) void file.text().then((text) => onFile(parseCsv(text))); }} /></label></div>;
}

function SummaryCards({ rows, postCreate = false }: { rows: ClassifiedImportRow[]; postCreate?: boolean }) {
  const values = importSummary(rows);
  const cards = postCreate ? { Created: values.created, "Needs Review": values.changed, "No Changes": values.noChanges, Invalid: values.invalid, Conflicts: values.conflicts } : { Total: values.total, New: values.new, Changed: values.changed, Identical: values.identical, Invalid: values.invalid, Conflicts: values.conflicts };
  return <div className="mb-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Import classification summary">{Object.entries(cards).map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800"><p className="text-xl font-bold">{value}</p><p className="text-xs text-slate-500">{label}</p></div>)}</div>;
}

function ResolvedPreviewTable({ rows }: { rows: ClassifiedImportRow[] }) {
  return <div className="max-h-[30rem] overflow-auto rounded-lg border"><table className="w-full min-w-[1000px] text-left text-xs"><thead className="sticky top-0 bg-slate-100 dark:bg-slate-800"><tr><th className="px-2 py-2">Row</th><th className="px-2 py-2">Readable identity</th><th className="px-2 py-2">Resolved references</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Message</th></tr></thead><tbody>{rows.slice(0, 300).map((row) => <tr key={row.rowNumber}><td className="border-t px-2 py-2">{row.rowNumber}</td><td className="border-t px-2 py-2 font-medium">{row.identityLabel}</td><td className="border-t px-2 py-2">{row.references.length ? row.references.map((reference) => <div key={`${reference.targetField}-${reference.original}`}>{reference.sourceColumns.join(" + ")}: {reference.resolvedLabel ?? reference.original}</div>) : "No foreign references"}</td><td className="border-t px-2 py-2"><Status value={row.status} /></td><td className="border-t px-2 py-2">{row.messages.join("; ") || (row.status === "IDENTICAL" ? "No Changes" : row.status === "CHANGED" ? `${row.differences.length} changed field(s); approval required.` : "Ready")}</td></tr>)}</tbody></table></div>;
}

function ReviewRows({ rows, busy, onUpdate, onKeep }: { rows: ClassifiedImportRow[]; busy: boolean; onUpdate(rowNumber: number): Promise<void>; onKeep(rowNumber: number): void }) {
  if (!rows.length) return <p className="rounded-lg bg-slate-50 p-6 text-center text-sm text-slate-500 dark:bg-slate-800">No rows in this category.</p>;
  return <div className="max-h-[32rem] space-y-3 overflow-auto">{rows.map((row) => <article key={row.rowNumber} className="rounded-lg border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold">Row {row.rowNumber}: {row.identityLabel}</p><div className="mt-1"><Status value={row.status} /></div></div>{row.status === "CHANGED" && <div className="flex gap-2"><button className="button-primary" disabled={busy} onClick={() => void onUpdate(row.rowNumber)}>Update</button><button className="button-secondary" disabled={busy} onClick={() => onKeep(row.rowNumber)}>Keep Existing</button></div>}</div>{row.differences.length > 0 && <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="py-1">Changed field</th><th>Existing</th><th>Imported</th></tr></thead><tbody>{row.differences.map((difference) => <tr key={difference.field}><td className="border-t py-2 font-medium">{difference.label}</td><td className="border-t py-2">{difference.existingLabel}</td><td className="border-t py-2">{difference.importedLabel}</td></tr>)}</tbody></table></div>}<ImportProblems errors={row.messages} /></article>)}</div>;
}

function Status({ value }: { value: ImportRowStatus }) { const colors: Record<ImportRowStatus, string> = { NEW: "bg-blue-100 text-blue-800", IDENTICAL: "bg-slate-100 text-slate-700", CHANGED: "bg-amber-100 text-amber-800", INVALID: "bg-red-100 text-red-800", CONFLICT: "bg-purple-100 text-purple-800", CREATED: "bg-emerald-100 text-emerald-800", UPDATED: "bg-emerald-100 text-emerald-800", KEPT_EXISTING: "bg-slate-100 text-slate-700", NO_CHANGES: "bg-slate-100 text-slate-700" }; const labels: Partial<Record<ImportRowStatus, string>> = { IDENTICAL: "NO CHANGES", KEPT_EXISTING: "KEPT EXISTING", NO_CHANGES: "NO CHANGES" }; return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${colors[value]}`}>{labels[value] ?? value}</span>; }
function ImportProblems({ errors }: { errors: string[] }) { return errors.length ? <div role="alert" className="mt-3 max-h-44 overflow-auto rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><ul className="list-disc pl-5">{errors.map((error, index) => <li key={`${error}-${index}`}>{error}</li>)}</ul></div> : null; }
function replaceRow(rows: ClassifiedImportRow[], rowNumber: number, replacement: ClassifiedImportRow) { return rows.map((row) => row.rowNumber === rowNumber ? replacement : row); }
function title(value: string) { return value.charAt(0) + value.slice(1).toLowerCase(); }
function isConflictMessage(value: string) { return /duplicate|already exists|conflict|changed since|ambiguous/i.test(value); }
function activityDependencyRank(config: MasterConfig, row: ClassifiedImportRow) { return config.slug === "laboratory-allocations" && row.payload.role_type === "SUPPORTING" ? 1 : 0; }

async function importLaboratorySlots(laboratory: { id: string }, source: Record<string, string>, lookups: Record<string, MasterRecord[]>, previous?: MasterRecord) {
  const resolution = resolveLaboratoryAvailabilityCsv(source, lookups);
  if (resolution.errors.length) throw new Error(resolution.errors.join("; "));
  const termIds = new Set(resolution.slots.map((slot) => slot.academic_term_id));
  const modeChanged = previous && String(previous.availability_mode ?? (previous.is_available_all_periods === false ? "EXCEPT_BLOCKED" : "ALL_PERIODS")) !== source.availability_mode;
  const existing = (lookups["/laboratory-availability-blocks"] ?? []).filter((row) => row.laboratory_id === laboratory.id && row.is_active !== false && (modeChanged || !termIds.size || termIds.has(String(row.academic_term_id))));
  for (const row of existing) await masterDataApi.remove(masterConfigs["lab-availability-blocks"], row.id);
  for (const slot of resolution.slots) await masterDataApi.create(masterConfigs["lab-availability-blocks"], { laboratory_id: laboratory.id, ...slot });
}
