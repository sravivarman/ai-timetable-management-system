"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { listAcademicTerms, masterApi, timetableApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { sectionLabel, sectionTerm } from "@/lib/section-labels";

type SearchItem = { id: string; label: string; kind: string; href: string };

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen(true); queueMicrotask(() => input.current?.focus()); } if (event.key === "Escape") setOpen(false); }; document.addEventListener("keydown", handler); return () => document.removeEventListener("keydown", handler); }, []);
  const query = useQuery({ queryKey: queryKeys.globalSearch(value), enabled: open && value.trim().length >= 2, queryFn: () => searchAll(value.trim()) });
  return <div className="relative print:hidden"><button className="button-secondary h-9 gap-2 px-3 text-xs" aria-expanded={open} aria-controls="global-search-panel" onClick={() => { setOpen(true); queueMicrotask(() => input.current?.focus()); }}><Search className="h-4 w-4" /><span className="hidden md:inline">Search</span><kbd className="hidden rounded bg-slate-100 px-1.5 py-0.5 text-[10px] lg:inline">Ctrl K</kbd></button>{open && <div id="global-search-panel" className="fixed inset-x-3 top-3 z-[80] mx-auto max-w-2xl rounded-xl border bg-white p-3 shadow-2xl dark:border-slate-700 dark:bg-slate-900 sm:top-20" role="dialog" aria-label="Global search"><div className="flex items-center gap-2"><Search className="h-5 w-5 text-slate-400" /><input ref={input} className="field border-0 text-base shadow-none ring-0" aria-label="Search timetables and academic resources" placeholder="Search timetable, version, section, faculty, room, lab, or course…" value={value} onChange={(event) => setValue(event.target.value)} /><button aria-label="Close search" className="rounded p-2 hover:bg-slate-100" onClick={() => setOpen(false)}><X className="h-4 w-4" /></button></div><div className="mt-2 max-h-[65vh] overflow-y-auto" role="listbox">{value.length < 2 ? <p className="p-4 text-sm text-slate-500">Type at least two characters.</p> : query.isLoading ? <p className="p-4 text-sm text-slate-500">Searching…</p> : !query.data?.length ? <p className="p-4 text-sm text-slate-500">No matching records.</p> : query.data.map((item) => <Link key={`${item.kind}-${item.id}`} role="option" className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-brand-50 dark:hover:bg-slate-800" href={item.href} onClick={() => setOpen(false)}><span className="text-sm font-medium">{item.label}</span><span className="text-xs uppercase text-slate-400">{item.kind}</span></Link>)}</div></div>}</div>;
}

async function searchAll(term: string): Promise<SearchItem[]> {
  const lower = term.toLowerCase();
  const [timetablePage, termPage, departmentPage, programPage, sectionPage, facultyPage, classroomPage, laboratoryPage, coursePage] = await Promise.all([safe(timetableApi.list({ page_size: 100 })), safe(listAcademicTerms()), safe(masterApi.departments()), safe(masterApi.programs()), safe(masterApi.sections()), safe(masterApi.faculty(term)), safe(masterApi.classrooms()), safe(masterApi.laboratories()), safe(masterApi.courses(term))]);
  const timetables = timetablePage?.items ?? [];
  const defaultVersion = timetables.find((item) => item.active_version_id)?.active_version_id;
  const reportHref = (report: string, id: string) => defaultVersion ? `/reports?report=${report}&version_id=${defaultVersion}&resource_id=${id}` : "/timetables";
  const items: SearchItem[] = [];
  for (const item of timetables.filter((item) => item.name.toLowerCase().includes(lower))) { items.push({ id: item.id, label: item.name, kind: "Timetable", href: `/timetables/${item.id}` }); if (item.active_version_id) items.push({ id: item.active_version_id, label: `${item.name} · active version`, kind: "Version", href: `/timetable-versions/${item.active_version_id}` }); }
  for (const item of (termPage?.items ?? []).filter((item) => `${item.academic_year} ${item.term_name}`.toLowerCase().includes(lower))) items.push({ id: item.id, label: `${item.academic_year} · ${item.term_name}`, kind: "Academic Term", href: `/master-data/academic-terms?search=${encodeURIComponent(term)}` });
  for (const item of (departmentPage?.items ?? []).filter((item) => `${item.department_code} ${item.department_name}`.toLowerCase().includes(lower))) items.push({ id: item.id, label: `${item.department_code} · ${item.department_name}`, kind: "Department", href: `/master-data/departments?search=${encodeURIComponent(term)}` });
  for (const item of (programPage?.items ?? []).filter((item) => `${item.program_code} ${item.program_name}`.toLowerCase().includes(lower))) items.push({ id: item.id, label: `${item.program_code} · ${item.program_name}`, kind: "Program", href: `/master-data/programs?search=${encodeURIComponent(term)}` });
  for (const item of (sectionPage?.items ?? []).filter((item) => sectionLabel(item, sectionTerm(item, termPage?.items)).toLowerCase().includes(lower))) items.push({ id: item.id, label: sectionLabel(item, sectionTerm(item, termPage?.items)), kind: "Section", href: reportHref("section-timetable", item.id) });
  for (const item of facultyPage?.items ?? []) items.push({ id: item.id, label: `${item.faculty_code} · ${item.full_name}`, kind: "Faculty", href: reportHref("faculty-timetable", item.id) });
  for (const item of (classroomPage?.items ?? []).filter((item) => `${item.room_number} ${item.room_name ?? ""}`.toLowerCase().includes(lower))) items.push({ id: item.id, label: `${item.room_number}${item.room_name ? ` · ${item.room_name}` : ""}`, kind: "Classroom", href: reportHref("classroom-utilization", item.id) });
  for (const item of (laboratoryPage?.items ?? []).filter((item) => `${item.laboratory_code} ${item.laboratory_name}`.toLowerCase().includes(lower))) items.push({ id: item.id, label: `${item.laboratory_code} · ${item.laboratory_name}`, kind: "Laboratory", href: reportHref("laboratory-utilization", item.id) });
  for (const item of coursePage?.items ?? []) items.push({ id: item.id, label: `${item.course_code} · ${item.course_name}`, kind: "Course", href: `/master-data/courses?search=${encodeURIComponent(item.course_code)}` });
  return items.slice(0, 30);
}

async function safe<T>(promise: Promise<T>): Promise<T | undefined> { try { return await promise; } catch { return undefined; } }
