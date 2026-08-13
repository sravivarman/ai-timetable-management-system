"use client";

import Link from "next/link";
import { useQueries, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Database } from "lucide-react";
import { Card, PageHeader } from "@/components/ui";
import { masterDataApi } from "@/lib/master-data-api";
import { dashboardModules, masterConfigs } from "@/lib/master-data-config";
import { validationApi } from "@/lib/api";

const groupedModules = [
  ["academic-terms", "Academic Terms"], ["departments", "Departments"], ["programs", "Programs"], ["sections", "Sections"],
  ["faculty", "Faculty"], ["courses", "Courses"], ["classrooms", "Classrooms"], ["laboratories", "Laboratories"],
  ["working-days", "Working Days"], ["period-timings", "Period Timings"], ["faculty-availability", "Faculty Availability"],
  ["faculty-scheduling-policies", "Faculty Scheduling Policies"], ["course-offerings", "Course Offerings"],
  ["faculty-allocations?variant=theory", "Faculty Allocations"], ["student-batches", "Student Batches"],
  ["laboratory-configuration?variant=batch-configurations", "Laboratory Configuration"], ["classroom-assignments", "Classroom Assignments"],
  ["lab-availability-blocks", "Lab Availability Blocks"],
] as const;

export default function MasterDataDashboard() {
  const modules = dashboardModules.map((key) => masterConfigs[key]);
  const counts = useQueries({ queries: modules.map((config) => ({ queryKey: ["master-dashboard-count", config.slug], queryFn: () => masterDataApi.list(config, { page: 1, page_size: 1 }), retry: false })) });
  const warnings = useQuery({ queryKey: ["master-dashboard-warnings"], queryFn: () => validationApi.list({ status: "WARNING", page: 1, page_size: 1 }), retry: false });
  return <>
    <PageHeader title="Master Data" description="Coordinator and administrator workspace for academic, people, facility, allocation, and scheduling reference data." />
    <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {modules.map((config, index) => <Link key={config.slug} href={dashboardHref(config.slug)} className="panel group p-5 transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-500">
        <div className="flex items-start justify-between gap-3"><Database className="h-5 w-5 text-brand-600" /><ArrowRight className="h-4 w-4 text-slate-400 transition group-hover:translate-x-1" /></div>
        <p className="mt-4 text-3xl font-bold">{counts[index].isLoading ? <span className="inline-block h-8 w-14 animate-pulse rounded bg-slate-200" /> : counts[index].isError ? "—" : counts[index].data?.total ?? 0}</p>
        <p className="mt-1 text-sm font-semibold">{config.slug === "theory-allocations" ? "Faculty Allocations" : config.label}</p>
        {counts[index].isError && <p className="mt-1 text-xs text-amber-700">Unavailable with current permissions</p>}
      </Link>)}
      <Link href="/validation?status=WARNING" className="panel group p-5 transition hover:border-amber-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-amber-500">
        <AlertTriangle className="h-5 w-5 text-amber-600" />
        <p className="mt-4 text-3xl font-bold">{warnings.isLoading ? <span className="inline-block h-8 w-14 animate-pulse rounded bg-slate-200" /> : warnings.isError ? "—" : warnings.data?.total ?? 0}</p>
        <p className="mt-1 text-sm font-semibold">Validation warnings</p>
      </Link>
    </div>
    <Card title="All master-data modules">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{groupedModules.map(([path, label]) => <Link key={path} className="flex items-center justify-between rounded-lg border px-4 py-3 text-sm font-semibold transition hover:border-brand-300 hover:bg-brand-50 dark:border-slate-700 dark:hover:bg-slate-800" href={`/master-data/${path}`}>{label}<ArrowRight className="h-4 w-4 text-slate-400" /></Link>)}</div>
    </Card>
  </>;
}

function dashboardHref(slug: string) {
  if (slug === "theory-allocations") return "/master-data/faculty-allocations?variant=theory";
  return `/master-data/${slug}`;
}
