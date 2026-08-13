import { describe, expect, it, vi } from "vitest";
import { downloadCsv, toCsv } from "@/lib/csv";

describe("browser CSV export", () => {
  it("escapes commas and quotes deterministically", () => { expect(toCsv([{ name: 'A, "B"', count: 2 }])).toBe('"name","count"\r\n"A, ""B""","2"'); });
  it("creates and revokes a downloadable object URL", () => { const create = vi.fn(() => "blob:report"); const revoke = vi.fn(); Object.defineProperty(URL, "createObjectURL", { value: create, configurable: true }); Object.defineProperty(URL, "revokeObjectURL", { value: revoke, configurable: true }); const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined); downloadCsv("report", [{ status: "PASSED" }]); expect(create).toHaveBeenCalled(); expect(click).toHaveBeenCalled(); expect(revoke).toHaveBeenCalledWith("blob:report"); });
});
