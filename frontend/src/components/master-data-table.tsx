"use client";

import { Eye, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { StatusBadge } from "@/components/ui";
import type { MasterRecord } from "@/lib/master-data-api";
import type { MasterColumn } from "@/lib/master-data-config";

type Props = {
  rows: MasterRecord[];
  columns: MasterColumn[];
  lookups: Record<string, Map<string, string>>;
  selected: Set<string>;
  onSelection(ids: Set<string>): void;
  sortKey: string;
  sortDirection: "asc" | "desc";
  onSort(key: string): void;
  canManage: boolean;
  onView(row: MasterRecord): void;
  onEdit(row: MasterRecord): void;
  onDuplicate(row: MasterRecord): void;
  onDelete(row: MasterRecord): void;
  onRestore(row: MasterRecord): void;
  onActivate?(row: MasterRecord): void;
};

export function MasterDataTable({ rows, columns, lookups, selected, onSelection, sortKey, sortDirection, onSort, canManage, onView, onEdit, onDuplicate, onDelete, onRestore, onActivate }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [widths, setWidths] = useState<Record<string, number>>({});
  const visible = columns.filter((column) => column.key !== "id" && !hidden.has(column.key));
  const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const toggleAll = () => onSelection(allSelected ? new Set() : new Set(rows.map((row) => row.id)));
  const resize = (key: string, start: number, event: React.PointerEvent) => {
    const origin = Number.isFinite(event.clientX) ? event.clientX : 0;
    const move = (next: PointerEvent) => { const clientX = Number.isFinite(next.clientX) ? next.clientX : origin; setWidths((current) => ({ ...current, [key]: Math.max(100, start + clientX - origin) })); };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return <div>
    <details className="relative mb-3 w-fit print:hidden">
      <summary className="button-secondary cursor-pointer list-none">Columns</summary>
      <div className="absolute left-0 z-30 mt-1 w-64 rounded-lg border bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-900">
        {columns.filter((column) => column.key !== "id").map((column) => <label key={column.key} className="flex items-center gap-2 py-1 text-sm"><input type="checkbox" checked={!hidden.has(column.key)} onChange={() => setHidden((current) => { const next = new Set(current); if (next.has(column.key)) next.delete(column.key); else next.add(column.key); return next; })} />{column.label}</label>)}
      </div>
    </details>
    <div className="max-h-[65vh] overflow-auto rounded-lg border dark:border-slate-700">
      <table className="w-full min-w-[900px] table-fixed text-left text-sm">
        <thead className="sticky top-0 z-20 bg-slate-100 text-xs uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300"><tr>
          <th className="w-12 px-3 py-3"><input aria-label="Select all visible rows" type="checkbox" checked={allSelected} onChange={toggleAll} /></th>
          {visible.map((column) => <th key={column.key} style={{ width: widths[column.key] ?? 170 }} className="relative px-3 py-3"><button className="w-full text-left" onClick={() => onSort(column.key)}>{column.label}{sortKey === column.key ? sortDirection === "asc" ? " ↑" : " ↓" : ""}</button><button aria-label={`Resize ${column.label} column`} className="absolute right-0 top-0 h-full w-2 cursor-col-resize hover:bg-brand-200" onPointerDown={(event) => resize(column.key, widths[column.key] ?? 170, event)} /></th>)}
          <th className="sticky right-0 w-72 bg-slate-100 px-3 py-3 text-right dark:bg-slate-800">Actions</th>
        </tr></thead>
        <tbody className="divide-y dark:divide-slate-700">{rows.map((row) => <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/70">
          <td className="px-3 py-3"><input aria-label={`Select ${display(row, visible[0], lookups)}`} type="checkbox" checked={selected.has(row.id)} onChange={() => onSelection(toggle(selected, row.id))} /></td>
          {visible.map((column) => <td key={column.key} className="truncate px-3 py-3" title={display(row, column, lookups)}>{column.key === "is_current" && onActivate ? <StatusBadge value={row.is_current === true ? "ACTIVE" : "INACTIVE"} /> : column.key === "is_active" ? <StatusBadge value={onActivate ? row.is_active === false ? "DISABLED" : "ENABLED" : row.is_active === false ? "INACTIVE" : "ACTIVE"} /> : column.key.startsWith("is_") ? String(Boolean(row[column.key]) ? "Yes" : "No") : display(row, column, lookups)}</td>)}
          <td className="sticky right-0 bg-white px-3 py-2 dark:bg-slate-900"><div className="flex justify-end gap-1">
            <Action label="View details" icon={<Eye />} onClick={() => onView(row)} />
            {canManage && <>
              <Action label="Duplicate" icon={<RotateCcw />} onClick={() => onDuplicate(row)} />
              {row.is_active === false ? <Action label="Restore" icon={<RotateCcw />} onClick={() => onRestore(row)} /> : <>
                <Action label="Edit" icon={<Pencil />} onClick={() => onEdit(row)} />
                {onActivate && (row.is_current === true ? <StatusBadge value="ACTIVE" /> : <button className="rounded px-2 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50" onClick={() => onActivate(row)}>Activate</button>)}
                <Action label="Delete" icon={<Trash2 />} destructive onClick={() => onDelete(row)} />
              </>}
            </>}
          </div></td>
        </tr>)}</tbody>
      </table>
    </div>
  </div>;
}

function Action({ label, icon, onClick, destructive = false }: { label: string; icon: ReactNode; onClick(): void; destructive?: boolean }) { return <button aria-label={label} title={label} className={`rounded p-2 hover:bg-slate-100 dark:hover:bg-slate-800 ${destructive ? "text-red-700" : "text-slate-600 dark:text-slate-300"}`} onClick={onClick}><span className="block h-4 w-4 [&>svg]:h-4 [&>svg]:w-4">{icon}</span></button>; }
function toggle(current: Set<string>, id: string) { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; }
function display(row: MasterRecord, column: MasterColumn | undefined, lookups: Record<string, Map<string, string>>) { if (!column) return "record"; const value = row[column.key]; if (value == null || value === "") return column.fallback ?? "—"; if (column.lookup) return lookups[column.lookup.endpoint]?.get(String(value)) ?? "Metadata unavailable"; if (Array.isArray(value)) return value.join(", "); if (typeof value === "object") return JSON.stringify(value); return String(value); }
