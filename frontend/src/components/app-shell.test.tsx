import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { renderWithProviders } from "@/test/render";

let role = "Timetable Coordinator";
vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ user: { full_name: role === "REPORT_VIEWER" ? "Report Viewer" : "Coordinator", roles: [{ name: role }] }, logout: vi.fn() }) }));
describe("responsive navigation", () => {
  it("opens and closes the accessible mobile sidebar", async () => { role = "Timetable Coordinator"; const user = userEvent.setup(); renderWithProviders(<AppShell><main>Content</main></AppShell>); const open = screen.getByRole("button", { name: "Open navigation" }); expect(open).toHaveAttribute("aria-expanded", "false"); await user.click(open); expect(open).toHaveAttribute("aria-expanded", "true"); await user.click(screen.getByRole("button", { name: "Close navigation" })); expect(open).toHaveAttribute("aria-expanded", "false"); });
  it("shows Report Viewer only Reports and Logout navigation", () => { role = "REPORT_VIEWER"; renderWithProviders(<AppShell><main>Content</main></AppShell>); expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports?report=administrative-faculty_master"); for (const name of ["Dashboard", "Timetables", "Validation", "Solver Runs", "Master Data", "Users", "Settings"]) expect(screen.queryByRole("link", { name })).not.toBeInTheDocument(); expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument(); expect(screen.queryByLabelText("Global search")).not.toBeInTheDocument(); });
});
