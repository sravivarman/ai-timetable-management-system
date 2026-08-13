"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

export function Breadcrumbs() {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length || pathname === "/dashboard") return null;
  return <nav aria-label="Breadcrumb" className="mb-4 print:hidden"><ol className="flex flex-wrap items-center gap-1 text-xs text-slate-500 dark:text-slate-400"><li><Link aria-label="Dashboard" href="/dashboard" className="inline-flex rounded p-1 hover:text-brand-700"><Home className="h-3.5 w-3.5" /></Link></li>{parts.map((part, index) => { const href = `/${parts.slice(0, index + 1).join("/")}`; const current = index === parts.length - 1; const label = /^[0-9a-f-]{20,}$/i.test(part) ? detailLabel(parts[index - 1]) : part.replaceAll("-", " "); return <li key={href} className="flex items-center gap-1"><ChevronRight className="h-3 w-3" />{current ? <span aria-current="page" className="capitalize text-slate-700 dark:text-slate-200">{label}</span> : <Link className="capitalize hover:text-brand-700" href={href}>{label}</Link>}</li>; })}</ol></nav>;
}

function detailLabel(parent?: string) {
  if (parent === "timetables") return "Timetable details";
  if (parent === "timetable-versions") return "Version details";
  if (parent === "validation") return "Validation details";
  if (parent === "solver-runs") return "Solver run details";
  return "Details";
}
