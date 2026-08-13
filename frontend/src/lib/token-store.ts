import type { TokenPair } from "@/lib/types";

const ACCESS_KEY = "ai_timetable_access_token";
const REFRESH_KEY = "ai_timetable_refresh_token";

function storage(): Storage | null { return typeof window === "undefined" ? null : window.localStorage }

export const tokenStore = {
  access: () => storage()?.getItem(ACCESS_KEY) ?? null,
  refresh: () => storage()?.getItem(REFRESH_KEY) ?? null,
  set(tokens: TokenPair) { storage()?.setItem(ACCESS_KEY, tokens.access_token); storage()?.setItem(REFRESH_KEY, tokens.refresh_token); this.notify() },
  clear() { storage()?.removeItem(ACCESS_KEY); storage()?.removeItem(REFRESH_KEY); this.notify() },
  hasSession: () => Boolean(storage()?.getItem(REFRESH_KEY)),
  subscribe(listener: () => void) { if (typeof window === "undefined") return () => undefined; window.addEventListener("auth-session-change", listener); return () => window.removeEventListener("auth-session-change", listener) },
  notify() { if (typeof window !== "undefined") window.dispatchEvent(new Event("auth-session-change")) },
};
