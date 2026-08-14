"use client";
import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { LoadingState } from "@/components/ui";

export function AuthGuard({ children }: { children: ReactNode }) { const { user, loading } = useAuth(); const router = useRouter(); const pathname = usePathname(); const reportViewer = Boolean(user?.roles.some((role) => role.name === "REPORT_VIEWER")); useEffect(() => { if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`); else if (!loading && reportViewer && pathname !== "/reports") router.replace("/reports?report=administrative-faculty_master") }, [loading, user, reportViewer, router, pathname]); if (loading || !user || reportViewer && pathname !== "/reports") return <main className="mx-auto max-w-md p-10"><LoadingState label="Restoring session" /></main>; return children }
