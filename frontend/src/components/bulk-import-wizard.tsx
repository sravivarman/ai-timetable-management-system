"use client";

import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Modal } from "@/components/ui";
import { parseCsv, type CsvPreview } from "@/lib/csv-import";
import { downloadCsv } from "@/lib/csv";
import { masterDataApi } from "@/lib/master-data-api";
import type { MasterConfig } from "@/lib/master-data-config";
import { apiErrorMessage } from "@/lib/api-client";
import {
  addDuplicateCsvErrors,
  csvTemplateColumns,
  findExistingImportRecord,
  importLookupEndpoints,
  requiredCsvColumns,
  resolveCsvImportRow,
  type ResolvedImportRow,
} from "@/lib/csv-import-resolution";
import { resolveLaboratoryAvailabilityCsv } from "@/lib/laboratory-availability-csv";
import { masterConfigs } from "@/lib/master-data-config";

type Summary = { inserted: number; updated: number; skipped: number; failed: number; errors: string[] };

export function BulkImportWizard({ config, onClose, onComplete }: { config: MasterConfig; onClose(): void; onComplete(): void }) {
  const [stage, setStage] = useState<"upload" | "preview" | "validation" | "import" | "summary">("upload");
  const [preview, setPreview] = useState<CsvPreview>({ headers: [], rows: [], errors: [] });
  const [summary, setSummary] = useState<Summary>({ inserted: 0, updated: 0, skipped: 0, failed: 0, errors: [] });
  const [busy, setBusy] = useState(false);
  const endpoints = useMemo(() => importLookupEndpoints(config), [config]);
  const lookupQueries = useQueries({ queries: endpoints.map((endpoint) => ({ queryKey: ["csv-import-lookup", endpoint], queryFn: () => masterDataApi.lookup(endpoint, true), staleTime: 60_000, retry: false })) });
  const lookupRecords = useMemo(() => Object.fromEntries(endpoints.map((endpoint, index) => [endpoint, lookupQueries[index].data ?? []])), [endpoints, lookupQueries]);
  const requiredMissing = useMemo(() => requiredCsvColumns(config).filter((column) => !preview.headers.includes(column)), [config, preview.headers]);
  const resolvedRows = useMemo(() => addDuplicateCsvErrors(config, preview.rows.map((row) => resolveCsvImportRow(config, row, lookupRecords))), [config, lookupRecords, preview.rows]);
  const lookupLoading = lookupQueries.some((query) => query.isLoading);
  const lookupErrors = lookupQueries.flatMap((query, index) => query.isError ? [`Could not load ${endpoints[index]} references: ${apiErrorMessage(query.error)}`] : []);
  const rowErrors = resolvedRows.flatMap((row, index) => row.errors.map((error) => `Row ${index + 2}: ${error}`));

  const importRows = async () => {
    setBusy(true); setStage("import");
    const result: Summary = { inserted: 0, updated: 0, skipped: 0, failed: 0, errors: [] };
    try {
      const [active, inactive] = await Promise.all([masterDataApi.all(config, { is_active: true }), masterDataApi.all(config, { is_active: false })]);
      const existing = [...new Map([...active, ...inactive].map((row) => [row.id, row])).values()];
      for (let index = 0; index < resolvedRows.length; index++) {
        const row = resolvedRows[index];
        if (row.errors.length) { result.skipped++; result.errors.push(`Row ${index + 2}: ${row.errors.join("; ")}`); continue; }
        const match = findExistingImportRecord(config, row.payload, existing);
        if (match.error) { result.skipped++; result.errors.push(`Row ${index + 2}: ${match.error}`); continue; }
        try {
          if (match.record) {
            const updated = await masterDataApi.update(config, match.record.id, row.payload);
            if (config.slug === "laboratories") await importLaboratorySlots(updated, row.source, lookupRecords, match.record);
            existing.splice(existing.indexOf(match.record), 1, updated);
            result.updated++;
          } else {
            const created = await masterDataApi.create(config, row.payload);
            if (config.slug === "laboratories") await importLaboratorySlots(created, row.source, lookupRecords);
            existing.push(created);
            result.inserted++;
          }
        } catch (error) {
          result.failed++;
          result.errors.push(`Row ${index + 2}: ${apiErrorMessage(error)}`);
        }
      }
    } catch (error) {
      result.failed += resolvedRows.filter((row) => !row.errors.length).length;
      result.errors.push(`Import preparation failed: ${apiErrorMessage(error)}`);
    }
    setSummary(result); setBusy(false); setStage("summary"); onComplete();
  };

  const blockingProblems = preview.errors.length > 0 || requiredMissing.length > 0 || lookupErrors.length > 0;
  return <Modal title={`Import ${config.label} from CSV`} onClose={onClose} wide footer={stage === "summary" ? <button className="button-primary" onClick={onClose}>Done</button> : <><button className="button-secondary" onClick={onClose} disabled={busy}>Cancel</button>{stage === "preview" && <button className="button-primary" disabled={blockingProblems || lookupLoading} onClick={() => setStage("validation")}>Validate</button>}{stage === "validation" && <button className="button-primary" disabled={blockingProblems || lookupLoading} onClick={() => void importRows()}>Import rows</button>}</>}>
    <ol className="mb-6 grid grid-cols-5 gap-2 text-center text-xs" aria-label="Import progress">{["Upload","Preview","Validation","Import","Summary"].map((label) => <li key={label} className={`rounded px-2 py-2 ${label.toLowerCase() === stage ? "bg-brand-600 text-white" : "bg-slate-100 dark:bg-slate-800"}`}>{label}</li>)}</ol>
    {stage === "upload" && <div className="space-y-4"><p className="text-sm text-slate-600 dark:text-slate-300">Upload UTF-8 CSV using institutional codes. Existing rows with the same business key are updated; UUIDs are resolved internally and never belong in the template.</p><p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">Academic terms use <strong>academic_term_code</strong> in the format <code>2026-27 | I-I</code>. Course offerings use course code, section code, and academic term code together.</p><button className="button-secondary" onClick={() => downloadCsv(`${config.slug}-template`, [Object.fromEntries(csvTemplateColumns(config).map((column) => [column, ""]))])}>Download readable-key template</button>{lookupLoading && <p role="status" className="text-sm">Loading reference dictionaries…</p>}<ImportProblems errors={lookupErrors} /><label className="block rounded-xl border-2 border-dashed p-8 text-center"><span className="block font-semibold">Choose CSV file</span><input aria-label="CSV file" className="mt-4" type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; void file.text().then((text) => { setPreview(parseCsv(text)); setStage("preview"); }); }} /></label></div>}
    {stage === "preview" && <><ImportProblems errors={[...preview.errors, ...lookupErrors, ...requiredMissing.map((column) => `Missing required column: ${column}`)]} /><p className="mb-3 text-sm">{preview.rows.length} rows detected. References are resolved against active backend records.</p><ResolvedPreviewTable rows={resolvedRows} /></>}
    {stage === "validation" && <><ImportProblems errors={rowErrors} /><p className="mb-3 text-sm font-semibold">{rowErrors.length ? `${resolvedRows.filter((row) => row.errors.length).length} rows will be skipped; valid rows may still be imported.` : `All ${resolvedRows.length} rows passed readable-key resolution and frontend validation.`}</p><ResolvedPreviewTable rows={resolvedRows} /></>}
    {stage === "import" && <div role="status" className="p-10 text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-brand-200 border-t-brand-600" /><p className="mt-4">Resolving business keys and importing through existing CRUD APIs…</p></div>}
    {stage === "summary" && <div><div className="grid gap-3 sm:grid-cols-4">{Object.entries({ Inserted: summary.inserted, Updated: summary.updated, Skipped: summary.skipped, Failed: summary.failed }).map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-4 text-center dark:bg-slate-800"><p className="text-2xl font-bold">{value}</p><p className="text-xs text-slate-500">{label}</p></div>)}</div><ImportProblems errors={summary.errors} /></div>}
  </Modal>;
}

async function importLaboratorySlots(laboratory: { id: string }, source: Record<string, string>, lookups: Record<string, import("@/lib/master-data-api").MasterRecord[]>, previous?: import("@/lib/master-data-api").MasterRecord) {
  const resolution = resolveLaboratoryAvailabilityCsv(source, lookups);
  if (resolution.errors.length) throw new Error(resolution.errors.join("; "));
  const termIds = new Set(resolution.slots.map((slot) => slot.academic_term_id));
  const modeChanged = previous && String(previous.availability_mode ?? (previous.is_available_all_periods === false ? "EXCEPT_BLOCKED" : "ALL_PERIODS")) !== source.availability_mode;
  const existing = (lookups["/laboratory-availability-blocks"] ?? []).filter((row) => row.laboratory_id === laboratory.id && row.is_active !== false && (modeChanged || !termIds.size || termIds.has(String(row.academic_term_id))));
  for (const row of existing) await masterDataApi.remove(masterConfigs["lab-availability-blocks"], row.id);
  for (const slot of resolution.slots) await masterDataApi.create(masterConfigs["lab-availability-blocks"], { laboratory_id: laboratory.id, ...slot });
}

function ImportProblems({ errors }: { errors: string[] }) { return errors.length ? <div role="alert" className="mb-4 max-h-44 overflow-auto rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><p className="font-semibold">Error list</p><ul className="mt-2 list-disc pl-5">{errors.map((error, index) => <li key={`${error}-${index}`}>{error}</li>)}</ul></div> : null; }

function ResolvedPreviewTable({ rows }: { rows: ResolvedImportRow[] }) {
  return <div className="max-h-96 overflow-auto rounded-lg border"><table className="w-full min-w-[1000px] text-left text-xs"><thead className="sticky top-0 bg-slate-100 dark:bg-slate-800"><tr><th className="px-2 py-2">Row</th><th className="px-2 py-2">Original CSV values</th><th className="px-2 py-2">Resolved readable records</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Row message</th></tr></thead><tbody>{rows.slice(0, 100).map((row, index) => <tr key={index}><td className="border-t px-2 py-2">{index + 2}</td><td className="border-t px-2 py-2">{Object.entries(row.source).filter(([, value]) => value).map(([key, value]) => <div key={key}><span className="font-medium">{key}:</span> {value}</div>)}</td><td className="border-t px-2 py-2">{row.references.length ? row.references.map((reference) => <div key={reference.targetField}><span className="font-medium">{reference.sourceColumns.join(" + ")}:</span> {reference.resolvedLabel ?? "Not resolved"}</div>) : "No foreign references"}</td><td className="border-t px-2 py-2"><span className={`rounded-full px-2 py-1 font-semibold ${row.errors.length ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"}`}>{row.errors.length ? "INVALID" : "READY"}</span></td><td className="border-t px-2 py-2 text-red-700">{row.errors.join("; ") || "Ready to import"}</td></tr>)}</tbody></table></div>;
}
