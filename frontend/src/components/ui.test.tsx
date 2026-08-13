import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "@/components/ui";

describe("accessible modal", () => {
  it("is labelled, modal, and closes with Escape", async () => { const close = vi.fn(); const user = userEvent.setup(); render(<Modal title="Confirm archive" onClose={close}><button>Confirm</button></Modal>); const dialog = screen.getByRole("dialog", { name: "Confirm archive" }); expect(dialog).toHaveAttribute("aria-modal", "true"); await user.keyboard("{Escape}"); expect(close).toHaveBeenCalledOnce(); });
});
