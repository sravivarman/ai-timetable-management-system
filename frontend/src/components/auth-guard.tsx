"use client";
import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { LoadingState } from "@/components/ui";

export function AuthGuard({ children }: { children: ReactNode }) { const { user, loading } = useAuth(); const router = useRouter(); const pathname = usePathname(); useEffect(() => { if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`) }, [loading, user, router, pathname]); if (loading || !user) return <main className="mx-auto max-w-md p-10"><LoadingState label="Restoring session" /></main>; return children }
