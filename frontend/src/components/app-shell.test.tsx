import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { renderWithProviders } from "@/test/render";

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ user: { full_name: "Coordinator", roles: [{ name: "Timetable Coordinator" }] }, logout: vi.fn() }) }));
describe("responsive navigation", () => {
  it("opens and closes the accessible mobile sidebar", async () => { const user = userEvent.setup(); renderWithProviders(<AppShell><main>Content</main></AppShell>); const open = screen.getByRole("button", { name: "Open navigation" }); expect(open).toHaveAttribute("aria-expanded", "false"); await user.click(open); expect(open).toHaveAttribute("aria-expanded", "true"); await user.click(screen.getByRole("button", { name: "Close navigation" })); expect(open).toHaveAttribute("aria-expanded", "false"); });
});
