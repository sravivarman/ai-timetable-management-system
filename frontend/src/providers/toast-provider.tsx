"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { X } from "lucide-react";

export type ToastTone = "success" | "warning" | "error" | "info";
type Toast = { id: number; message: string; tone: ToastTone };
const ToastContext = createContext<{ notify(message: string, tone?: ToastTone): void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setItems((current) => current.filter((item) => item.id !== id)), []);
  const notify = useCallback((message: string, tone: ToastTone = "success") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => dismiss(id), 4500);
  }, [dismiss]);
  const value = useMemo(() => ({ notify }), [notify]);
  return <ToastContext.Provider value={value}>{children}<div className="fixed bottom-4 right-4 z-[100] space-y-2" aria-live="polite" aria-atomic="false">{items.map((item) => <div key={item.id} role={item.tone === "error" ? "alert" : "status"} className={`flex max-w-sm items-start gap-3 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${item.tone === "error" ? "bg-red-700" : item.tone === "warning" ? "bg-amber-700" : item.tone === "info" ? "bg-slate-800" : "bg-emerald-700"}`}><span>{item.message}</span><button aria-label="Dismiss notification" className="ml-auto rounded p-0.5 hover:bg-white/20" onClick={() => dismiss(item.id)}><X className="h-4 w-4" /></button></div>)}</div></ToastContext.Provider>;
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
}
