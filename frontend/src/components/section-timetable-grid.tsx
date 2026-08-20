"use client";

import clsx from "clsx";
import { Lock, Pencil } from "lucide-react";
import type { GridEntry, TimetableGrid } from "@/lib/types";
import { EmptyState, StatusBadge } from "@/components/ui";

const tones: Record<string, string> = {
  THEORY: "border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/60",
  LABORATORY: "border-violet-300 bg-violet-50 dark:border-violet-700 dark:bg-violet-950/60",
  PRACTICAL: "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/60",
  CDC: "border-cyan-300 bg-cyan-50 dark:border-cyan-700 dark:bg-cyan-950/60",
  PROJECT: "border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/60",
  MINI_PROJECT: "border-teal-300 bg-teal-50 dark:border-teal-700 dark:bg-teal-950/60",
  LSM: "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/60",
};

export function SectionTimetableGrid({ grid, printable = true }: { grid: TimetableGrid; printable?: boolean }) {
  if (!grid.days.some((day) => day.entries.length)) return <EmptyState title="No scheduled entries" detail={`This ${grid.view_type} has no entries in the selected version.`} />;
  return <div className="timetable-visualization">
    <div className="mb-3 flex flex-wrap gap-2 text-xs print:hidden" aria-label="Timetable legend">{Object.keys(tones).map((type) => <span key={type} className={clsx("rounded border px-2 py-1", tones[type])}>{type.replaceAll("_", " ")}</span>)}<span className="rounded border border-violet-500 px-2 py-1"><Lock className="mr-1 inline h-3 w-3" />Locked</span><span className="rounded border border-dashed border-slate-500 px-2 py-1"><Pencil className="mr-1 inline h-3 w-3" />Manual</span></div>
    <div className={clsx("overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700", printable && "print:overflow-visible print:border-0")} tabIndex={0} aria-label={`Scrollable ${grid.scheduling_mode === "SLOT_BASED" ? "date-specific" : "weekly"} timetable`}>
      <table className="weekly-grid w-full min-w-[1050px] table-fixed border-collapse text-sm print:min-w-0"><thead><tr className="bg-slate-100 dark:bg-slate-800"><th className="sticky left-0 top-0 z-20 w-32 border-b border-r bg-slate-100 p-3 text-left dark:border-slate-700 dark:bg-slate-800">{grid.scheduling_mode === "SLOT_BASED" ? "Date / day" : "Day"}</th>{Array.from({ length: 7 }, (_, index) => <th key={index} className="sticky top-0 z-10 border-b border-r bg-slate-100 p-3 text-center dark:border-slate-700 dark:bg-slate-800">Period {index + 1}</th>)}</tr></thead><tbody>{grid.days.map((day) => {
        const starts = new Map<number, GridEntry[]>(); for (const entry of day.entries) starts.set(entry.period_number, [...(starts.get(entry.period_number) ?? []), entry]);
        const covered = new Set(day.entries.flatMap((entry) => entry.period_numbers.slice(1))); const cells = [];
        for (let period = 1; period <= 7; period++) { if (covered.has(period)) continue; const entries = starts.get(period) ?? []; cells.push(entries.length ? <EntryCell key={entries.map((entry) => entry.entry_id).join("-")} entries={entries} /> : <td key={period} className="h-28 border-b border-r bg-white p-2 text-center text-slate-300 dark:border-slate-700 dark:bg-slate-900">—</td>); }
        return <tr key={day.actual_date ?? day.working_day_id}><th className="sticky left-0 z-10 border-b border-r bg-slate-50 p-3 text-left align-top font-semibold dark:border-slate-700 dark:bg-slate-800">{day.actual_date && <span className="block">{formatDate(day.actual_date)}</span>}<span className={day.actual_date ? "text-xs font-normal text-slate-500" : ""}>{day.day_name}</span></th>{cells}</tr>;
      })}</tbody></table>
    </div>
  </div>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`)); }

function EntryCell({ entries }: { entries: GridEntry[] }) {
  const parallel = entries.length > 1 && entries.every((entry) => entry.laboratory_rotation_block_id && entry.laboratory_rotation_block_id === entries[0].laboratory_rotation_block_id);
  return <td colSpan={Math.max(...entries.map((entry) => entry.session_length))} className="border-b border-r p-1.5 align-top dark:border-slate-700">{parallel && <div className="mb-1 rounded bg-violet-100 px-2 py-1 text-[10px] font-bold uppercase text-violet-800 dark:bg-violet-950">Synchronized rotation block · {entries.length} parallel groups</div>}<div className={clsx(parallel && "grid gap-1 sm:grid-cols-2")}>{entries.map((entry) => <EntryCard key={entry.entry_id} entry={entry} />)}</div></td>;
}

function EntryCard({ entry }: { entry: GridEntry }) {
  const facility = entry.laboratory_code ?? entry.classroom_room_number;
  const combinedSections = entry.combined_section_codes?.length ? entry.combined_section_codes.join(" + ") : null;
  return <article tabIndex={0} aria-label={`${entry.course_code} ${entry.course_name}, ${entry.actual_date ? `${formatDate(entry.actual_date)} ` : ""}${entry.day_name}, periods ${entry.period_numbers.join(", ")}`} className={clsx("group relative min-h-24 rounded-lg border p-2.5 shadow-sm", tones[entry.course_type] ?? "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800", entry.is_locked && "ring-2 ring-violet-500", entry.is_manual && "border-dashed border-slate-600")}>
    <div className="flex items-start justify-between gap-2"><strong className="text-xs">{entry.course_code}</strong><span className="flex gap-1">{entry.is_manual && <Pencil aria-label="Manual entry" className="h-3.5 w-3.5" />}{entry.is_locked && <Lock aria-label="Locked entry" className="h-3.5 w-3.5 text-violet-700" />}</span></div>
    {combinedSections && <p className="mt-1 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">Combined: {combinedSections}</p>}
    <p className="mt-1 line-clamp-2 text-xs text-slate-700 dark:text-slate-200">{entry.course_name}</p>
    <p className="mt-2 text-[11px] text-slate-600 dark:text-slate-300">{entry.faculty_code ?? "No faculty"}{facility && ` · ${facility}`}{entry.batch_name && ` · ${entry.batch_name}`}</p>
    {entry.concurrent_usage_mode === "CAPACITY_SHARED" && entry.resource_capacity != null && <p className="mt-1 text-[11px] font-semibold text-violet-800 dark:text-violet-200">Occupancy: {entry.occupied_capacity ?? 0} / {entry.resource_capacity} <span className="font-normal">({entry.capacity_demand ?? 0} students in this activity)</span></p>}
    <div role="tooltip" className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 hidden w-72 -translate-x-1/2 rounded-lg bg-slate-950 p-3 text-left text-xs text-white shadow-xl group-hover:block group-focus:block print:hidden"><p className="font-semibold">{entry.course_code} · {entry.course_name}</p><dl className="mt-2 grid grid-cols-[auto,1fr] gap-x-2 gap-y-1"><dt>Type</dt><dd>{entry.course_type.replaceAll("_", " ")}</dd><dt>{combinedSections ? "Sections" : "Section"}</dt><dd>{combinedSections ?? entry.section_code}</dd>{entry.combined_teaching_group_code && <><dt>Common class</dt><dd>{entry.combined_teaching_group_code}</dd></>}<dt>Faculty</dt><dd>{[entry.faculty_code, entry.faculty_name].filter(Boolean).join(" · ") || "Not assigned"}</dd><dt>Periods</dt><dd>{entry.period_numbers.join(", ")} ({entry.start_time}–{entry.end_time})</dd><dt>Facility</dt><dd>{facility ?? "Not assigned"}</dd><dt>Student group</dt><dd>{entry.batch_name ?? "Full section"}</dd><dt>Status</dt><dd><StatusBadge value={entry.entry_status} /></dd>{entry.resource_capacity != null && <><dt>Occupancy</dt><dd>{entry.occupied_capacity ?? 0} / {entry.resource_capacity} students</dd></>}</dl></div>
  </article>;
}
