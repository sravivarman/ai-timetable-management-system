import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import { renderWithProviders } from "@/test/render";

const login = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => ({ login, user: null, loading: false }) }));

describe("username login", () => {
  it("uses a text Username field and submits the username", async () => {
    const user = userEvent.setup();
    login.mockResolvedValue(undefined);
    renderWithProviders(<LoginPage />);
    const username = screen.getByLabelText("Username");
    expect(username).toHaveAttribute("type", "text");
    expect(username).toHaveAttribute("placeholder", "Enter username");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    await user.type(username, "administrator");
    await user.type(screen.getByLabelText("Password"), "ExistingPassword123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("administrator", "ExistingPassword123"));
  });

  it("does not expose whether the username or password was incorrect", async () => {
    const user = userEvent.setup();
    login.mockRejectedValue(new Error("account not found"));
    renderWithProviders(<LoginPage />);
    await user.type(screen.getByLabelText("Username"), "unknown");
    await user.type(screen.getByLabelText("Password"), "WrongPassword123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username or password.");
  });
});
