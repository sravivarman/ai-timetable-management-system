"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, CalendarDays, CheckCircle2, FileBarChart, LayoutDashboard, LogOut, Menu, Moon, Settings, SlidersHorizontal, Sun, UserCog, X } from "lucide-react";
import { useEffect, useRef, useState, type ComponentType } from "react";
import clsx from "clsx";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { GlobalSearch } from "@/components/global-search";
import { useAuth } from "@/providers/auth-provider";

type NavItem = { label: string; href: string; icon: ComponentType<{ className?: string }>; roles?: string[] };
const administrators = ["Administrator", "System Administrator"];
const items: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Timetables", href: "/timetables", icon: CalendarDays, roles: [...administrators, "Timetable Coordinator", "HOD", "Dean", "Principal"] },
  { label: "Validation", href: "/validation", icon: CheckCircle2, roles: [...administrators, "Timetable Coordinator", "HOD", "Dean", "Principal"] },
  { label: "Solver Runs", href: "/solver-runs", icon: SlidersHorizontal, roles: [...administrators, "Timetable Coordinator", "HOD", "Dean", "Principal"] },
  { label: "Master Data", href: "/master-data", icon: BookOpen, roles: [...administrators, "Timetable Coordinator", "HOD"] },
  { label: "Users", href: "/users", icon: UserCog, roles: administrators },
  { label: "Reports", href: "/reports", icon: FileBarChart },
  { label: "Settings", href: "/settings", icon: Settings, roles: administrators },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const roles = user?.roles.map((role) => role.name) ?? [];
  const visible = items.filter((item) => !item.roles || item.roles.some((role) => roles.includes(role)));
  useEffect(() => { const stored = localStorage.getItem("vce-theme"); const enabled = stored === "dark" || (!stored && Boolean(window.matchMedia?.("(prefers-color-scheme: dark)").matches)); setDark(enabled); document.documentElement.classList.toggle("dark", enabled); }, []);
  useEffect(() => { if (open) closeButton.current?.focus(); }, [open]);
  const toggleTheme = () => setDark((current) => { const next = !current; document.documentElement.classList.toggle("dark", next); localStorage.setItem("vce-theme", next ? "dark" : "light"); return next; });
  return <div className="min-h-screen bg-slate-50 dark:bg-slate-950 dark:text-slate-100">
    {open && <button aria-label="Close navigation overlay" className="fixed inset-0 z-30 bg-slate-950/50 lg:hidden" onClick={() => setOpen(false)} />}
    <aside aria-label="Primary navigation" className={clsx("fixed inset-y-0 left-0 z-40 w-64 border-r border-slate-800 bg-slate-950 text-white transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
      <div className="flex h-16 items-center justify-between border-b border-slate-800 px-5"><div><p className="font-semibold">AI Timetable</p><p className="text-xs text-slate-400">VCE Academic Planning</p></div><button ref={closeButton} aria-label="Close navigation" className="rounded p-2 hover:bg-slate-800 lg:hidden" onClick={() => setOpen(false)}><X /></button></div>
      <nav className="space-y-1 p-3" aria-label="Main navigation">{visible.map(({ label, href, icon: Icon }) => <Link key={href} href={href} onClick={() => setOpen(false)} className={clsx("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm", pathname.startsWith(href) ? "bg-brand-600 font-semibold" : "text-slate-300 hover:bg-slate-800 hover:text-white")}><Icon className="h-4 w-4" />{label}</Link>)}</nav>
    </aside>
    <div className="lg:pl-64"><header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95 sm:px-6 print:hidden"><button aria-label="Open navigation" aria-expanded={open} className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800 lg:hidden" onClick={() => setOpen(true)}><Menu /></button><p className="hidden min-w-0 truncate font-semibold text-brand-900 dark:text-slate-100 xl:block">AI-Based Engineering College Timetable Management System</p><div className="ml-auto flex items-center gap-2"><GlobalSearch /><button className="button-secondary h-9 px-2" aria-label={`Use ${dark ? "light" : "dark"} theme`} onClick={toggleTheme}>{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button><div className="hidden text-right sm:block"><p className="text-sm font-medium">{user?.full_name}</p><p className="max-w-52 truncate text-xs text-slate-500">{roles.join(", ")}</p></div><button className="button-secondary h-9 gap-2" onClick={() => void logout()}><LogOut className="h-4 w-4" /><span className="hidden md:inline">Logout</span></button></div></header><main className="mx-auto max-w-[1500px] p-4 sm:p-6"><Breadcrumbs />{children}</main></div>
  </div>;
}
