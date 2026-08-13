"use client";

import { useMemo, useState } from "react";
import { EmptyState, StatusBadge } from "@/components/ui";
import type { TimetableEntry, TimetableGrid } from "@/lib/types";
import { EntryActions } from "@/components/entry-actions";

export function EntriesPanel({ entries, grid, versionId, editable = false, disabledReason, canAudit = true }: { entries: TimetableEntry[]; grid?: TimetableGrid; versionId?: string; editable?: boolean; disabledReason?: string; canAudit?: boolean }) {
  const [type, setType] = useState("");
  const [day, setDay] = useState("");
  const [faculty, setFaculty] = useState("");
  const [batch, setBatch] = useState("");
  const [locked, setLocked] = useState("");
  const [manual, setManual] = useState("");

  const readable = useMemo(
    () => new Map(grid?.days.flatMap((item) => item.entries).map((item) => [item.entry_id, item]) ?? []),
    [grid],
  );
  const facultyLabels = new Map<string, string>();
  const batchLabels = new Map<string, string>();
  entries.forEach((entry) => {
    const detail = readable.get(entry.id);
    if (entry.faculty_id) facultyLabels.set(entry.faculty_id, detail?.faculty_code ?? "Faculty metadata unavailable");
    if (entry.student_batch_id) batchLabels.set(entry.student_batch_id, detail?.batch_name ?? "Batch metadata unavailable");
  });

  const rows = entries.filter((entry) =>
    (!type || entry.entry_type === type) &&
    (!day || entry.working_day_id === day) &&
    (!faculty || entry.faculty_id === faculty) &&
    (!batch || entry.student_batch_id === batch) &&
    (!locked || String(entry.is_locked) === locked) &&
    (!manual || String(entry.is_manual) === manual),
  );

  return <>
    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <Filter label="Entry type" value={type} onChange={setType} options={["THEORY", "LABORATORY", "PRACTICAL", "CDC", "LSM", "PROJECT", "MINI_PROJECT"]} />
      <Filter label="Working day" value={day} onChange={setDay} options={grid?.days.map((item) => [item.working_day_id, item.day_name]) ?? []} />
      <Filter label="Faculty" value={faculty} onChange={setFaculty} options={Array.from(facultyLabels)} />
      <Filter label="Batch" value={batch} onChange={setBatch} options={Array.from(batchLabels)} />
      <Filter label="Lock status" value={locked} onChange={setLocked} options={[["true", "Locked"], ["false", "Unlocked"]]} />
      <Filter label="Source" value={manual} onChange={setManual} options={[["true", "Manual"], ["false", "Generated"]]} />
    </div>
    {!rows.length ? <EmptyState title="No matching entries" /> : <div className="overflow-x-auto rounded-xl border">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Day / period", "Course", "Faculty", "Facility", "Batch", "Length", "Source", "Lock", "Actions"].map((heading) => <th key={heading} className="px-3 py-3">{heading}</th>)}</tr></thead>
        <tbody className="divide-y">{rows.map((row) => {
          const detail = readable.get(row.id);
          return <tr key={row.id} id={`entry-${row.id}`}>
            <td className="px-3 py-3">{detail?.day_name ?? "Working day unavailable"} · P{row.period_number}</td>
            <td className="px-3 py-3"><p className="font-medium">{detail?.course_code ?? "Course metadata unavailable"}</p><p className="text-xs text-slate-500">{detail?.course_name ?? row.entry_type}</p>{detail?.combined_section_codes?.length && <p className="mt-1 text-xs font-semibold text-indigo-700">Combined: {detail.combined_section_codes.join(" + ")}</p>}</td>
            <td className="px-3 py-3">{detail?.faculty_code ?? (row.faculty_id ? "Faculty metadata unavailable" : "—")}</td>
            <td className="px-3 py-3">{detail?.laboratory_code ?? detail?.classroom_room_number ?? ((row.laboratory_id || row.classroom_id) ? "Facility metadata unavailable" : "—")}</td>
            <td className="px-3 py-3">{detail?.batch_name ?? (row.student_batch_id ? "Batch metadata unavailable" : "—")}</td>
            <td className="px-3 py-3">{row.session_length}</td>
            <td className="px-3 py-3"><StatusBadge value={row.is_manual ? "MANUAL" : "GENERATED"} /></td>
            <td className="px-3 py-3"><StatusBadge value={row.is_locked ? "LOCKED" : "UNLOCKED"} /></td>
            <td className="px-3 py-3">{versionId && <EntryActions entry={row} versionId={versionId} sectionId={grid?.resource_id} editable={editable} disabledReason={disabledReason} canAudit={canAudit} />}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>}
  </>;
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: (string | [string, string])[] }) {
  return <select className="field" aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
    <option value="">All {label.toLowerCase()}</option>
    {options.map((option) => {
      const [optionValue, optionLabel] = Array.isArray(option) ? option : [option, option];
      return <option key={optionValue} value={optionValue}>{optionLabel}</option>;
    })}
  </select>;
}
