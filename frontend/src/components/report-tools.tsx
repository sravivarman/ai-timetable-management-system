"use client";

import { Download, Printer, RefreshCw } from "lucide-react";
import { downloadCsv } from "@/lib/csv";

export function ReportTools({ filename, rows, refresh, refreshing = false }: { filename: string; rows?: Record<string, unknown>[]; refresh?: () => void; refreshing?: boolean }) {
  return <div className="flex flex-wrap gap-2 print:hidden">{refresh && <button className="button-secondary gap-2" disabled={refreshing} onClick={refresh}><RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />Refresh</button>}<button className="button-secondary gap-2" onClick={() => window.print()}><Printer className="h-4 w-4" />Print</button><button className="button-secondary gap-2" disabled={!rows?.length} onClick={() => downloadCsv(filename, rows ?? [])}><Download className="h-4 w-4" />Export CSV</button></div>;
}
