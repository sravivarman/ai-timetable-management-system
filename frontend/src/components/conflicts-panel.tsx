import { CheckCircle2, TriangleAlert } from "lucide-react";
import { StatusBadge } from "@/components/ui";
import type { Conflict, ConflictReport, TimetableEntry, TimetableGrid } from "@/lib/types";

export function ConflictsPanel({ report, entries = [], grid }: { report: ConflictReport; entries?: TimetableEntry[]; grid?: TimetableGrid }) {
  const raw = new Map(entries.map((entry) => [entry.id, entry]));
  const rendered = new Map(grid?.days.flatMap((day) => day.entries).map((entry) => [entry.entry_id, entry]) ?? []);
  if (!report.conflicts.length) return <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-8 text-center text-emerald-800"><CheckCircle2 className="mx-auto mb-2 h-8 w-8" /><p className="font-semibold">No persisted timetable conflicts detected</p></div>;
  const grouped = report.conflicts.reduce<Record<string, Conflict[]>>((result, conflict) => { (result[conflict.conflict_type] ??= []).push(conflict); return result; }, {});
  return <div>
    <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-4 text-red-800"><TriangleAlert /><strong>{report.summary.total ?? report.conflicts.length} conflicts require attention</strong></div>
    <div className="space-y-5">{Object.entries(grouped).map(([type, conflicts]) => <section key={type}>
      <div className="mb-2 flex items-center gap-2"><StatusBadge value={type} /><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold">{conflicts.length}</span></div>
      <div className="space-y-3">{conflicts.map((conflict, index) => {
        const entryId = conflict.entry_ids[0];
        const detail = rendered.get(entryId);
        const entry = raw.get(entryId);
        const slot = conflict.day_name && conflict.period_number ? `${conflict.day_name} · P${conflict.period_number}` : detail ? `${detail.day_name} · P${detail.period_number}` : entry ? `Working day unavailable · P${entry.period_number}` : "Persisted entry";
        return <article key={`${type}-${index}`} className="panel p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-semibold">{conflict.affected_entity ?? type.replaceAll("_", " ")}</span><span className="text-xs text-slate-500">{slot}</span></div><p className="mt-2 text-sm">{conflict.message}</p><div className="mt-2 flex flex-wrap gap-2 text-xs">{conflict.entry_ids.map((id, entryIndex) => <a key={id} className="text-brand-700 underline" href={`#entry-${id}`}>Open entry {entryIndex + 1}</a>)}</div></article>;
      })}</div>
    </section>)}</div>
  </div>;
}
