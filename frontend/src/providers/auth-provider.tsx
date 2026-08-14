"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { tokenStore } from "@/lib/token-store";
import type { User } from "@/lib/types";

interface AuthContextValue { user: User | null; loading: boolean; login(username: string, password: string): Promise<void>; logout(): Promise<void>; hasRole(...roles: string[]): boolean }
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter(); const [user, setUser] = useState<User | null>(null); const [loading, setLoading] = useState(true);
  const restore = useCallback(async () => { if (!tokenStore.hasSession()) { setUser(null); setLoading(false); return } try { setUser(await authApi.me()) } catch { tokenStore.clear(); setUser(null) } finally { setLoading(false) } }, []);
  useEffect(() => { void restore(); return tokenStore.subscribe(() => { if (!tokenStore.hasSession()) setUser(null) }) }, [restore]);
  const login = useCallback(async (username: string, password: string) => { tokenStore.set(await authApi.login(username, password)); const authenticated = await authApi.me(); setUser(authenticated); router.replace(authenticated.roles.some((role) => role.name === "REPORT_VIEWER") ? "/reports?report=administrative-faculty_master" : "/dashboard") }, [router]);
  const logout = useCallback(async () => { try { if (tokenStore.access()) await authApi.logout() } finally { tokenStore.clear(); setUser(null); router.replace("/login") } }, [router]);
  const value = useMemo(() => ({ user, loading, login, logout, hasRole: (...roles: string[]) => Boolean(user?.roles.some((role) => roles.includes(role.name))) }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used within AuthProvider"); return value }
