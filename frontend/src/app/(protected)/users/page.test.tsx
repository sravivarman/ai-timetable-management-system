import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UsersPage from "@/app/(protected)/users/page";
import { usersAdminApi } from "@/lib/api";
import { renderWithProviders } from "@/test/render";

const authState = vi.hoisted(() => ({ isAdministrator: true }));
vi.mock("@/lib/api", () => ({ usersAdminApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), roles: vi.fn() } }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ hasRole: (...names: string[]) => authState.isAdministrator && names.includes("Administrator") }) }));

const permissions: never[] = [];
const roles = [
  { id: "admin-role", name: "Administrator", permissions },
  { id: "principal-role", name: "Principal", permissions },
  { id: "dean-role", name: "Dean", permissions },
  { id: "coordinator-role", name: "Timetable Coordinator", permissions },
  { id: "faculty-role", name: "Faculty", permissions },
  { id: "student-role", name: "Student", permissions },
];
const administrator = { id: "user-1", email: "admin@vce.ac.in", full_name: "System Administrator", is_active: true, roles: [roles[0]] };

describe("approved login account administration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.isAdministrator = true;
    vi.mocked(usersAdminApi.list).mockResolvedValue([administrator]);
    vi.mocked(usersAdminApi.roles).mockResolvedValue(roles);
    vi.mocked(usersAdminApi.get).mockResolvedValue(administrator);
  });

  it("lists readable users and exposes only approved login roles", async () => {
    const user = userEvent.setup();
    renderWithProviders(<UsersPage />);
    expect(await screen.findByText("System Administrator")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create login account" }));
    const roleSelect = screen.getByLabelText("Approved login role");
    expect(within(roleSelect).getByRole("option", { name: "Dean Academics" })).toBeInTheDocument();
    expect(within(roleSelect).queryByRole("option", { name: "Faculty" })).not.toBeInTheDocument();
    expect(within(roleSelect).queryByRole("option", { name: "Student" })).not.toBeInTheDocument();
  });

  it("creates a login account with exactly one approved role", async () => {
    vi.mocked(usersAdminApi.create).mockResolvedValue({ ...administrator, id: "user-2", email: "dean@vce.ac.in", full_name: "Dean Academics", roles: [roles[2]] });
    const user = userEvent.setup();
    renderWithProviders(<UsersPage />);
    await screen.findByText("System Administrator");
    await user.click(screen.getByRole("button", { name: "Create login account" }));
    await user.type(screen.getByLabelText("Full name"), "Dean Academics");
    await user.type(screen.getByLabelText("Email"), "dean@vce.ac.in");
    await user.selectOptions(screen.getByLabelText("Approved login role"), "dean-role");
    await user.type(screen.getByLabelText("Password"), "StrongPassword123");
    await user.click(screen.getByRole("button", { name: "Save account" }));
    await waitFor(() => expect(usersAdminApi.create).toHaveBeenCalledWith({ email: "dean@vce.ac.in", full_name: "Dean Academics", password: "StrongPassword123", role_ids: ["dean-role"] }));
  });

  it("supports search, status changes, editing, password reset, and deletion", async () => {
    vi.mocked(usersAdminApi.update).mockResolvedValue({ ...administrator, is_active: false });
    vi.mocked(usersAdminApi.remove).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderWithProviders(<UsersPage />);
    await screen.findByText("System Administrator");
    await user.type(screen.getByLabelText("Search users"), "missing");
    expect(screen.getByText("No login accounts found")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search users"));
    await user.click(screen.getByRole("button", { name: "Deactivate System Administrator" }));
    expect(usersAdminApi.update).toHaveBeenCalledWith("user-1", { is_active: false });
    await user.click(screen.getByRole("button", { name: "Edit System Administrator" }));
    expect(await screen.findByLabelText("Reset password")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Delete System Administrator" }));
    expect(usersAdminApi.remove).toHaveBeenCalledWith("user-1");
  });

  it("does not expose account actions to non-administrators", () => {
    authState.isAdministrator = false;
    renderWithProviders(<UsersPage />);
    expect(screen.getByText("You do not have permission to manage login accounts.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create login account" })).not.toBeInTheDocument();
    expect(usersAdminApi.list).not.toHaveBeenCalled();
  });
});
