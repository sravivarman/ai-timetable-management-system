import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "@/lib/token-store";
import type { TokenPair } from "@/lib/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
export const api = axios.create({ baseURL: API_BASE_URL, timeout: 20_000, headers: { Accept: "application/json" } });

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.access();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };
let refreshPromise: Promise<string> | null = null;
async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStore.refresh();
  if (!refreshToken) throw new Error("No refresh token");
  const { data } = await axios.post<TokenPair>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
  tokenStore.set(data);
  return data.access_token;
}

api.interceptors.response.use((response) => response, async (error: AxiosError) => {
  const config = error.config as RetryConfig | undefined;
  if (error.response?.status !== 401 || !config || config._retry || config.url?.includes("/auth/")) return Promise.reject(error);
  config._retry = true;
  try {
    refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null });
    config.headers.Authorization = `Bearer ${await refreshPromise}`;
    return api(config);
  } catch (refreshError) {
    tokenStore.clear();
    if (typeof window !== "undefined") window.location.assign("/login");
    return Promise.reject(refreshError);
  }
});

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)).join("; ");
    if (error.response?.status === 403) return "You do not have permission to perform this action.";
    return error.message || "The server request failed.";
  }
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}
