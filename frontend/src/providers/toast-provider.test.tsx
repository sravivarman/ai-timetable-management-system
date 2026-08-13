import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ToastProvider, useToast } from "@/providers/toast-provider";

function Trigger() { const { notify } = useToast(); return <div><button onClick={() => notify("Saved", "success")}>Success</button><button onClick={() => notify("Review warning", "warning")}>Warning</button></div>; }
describe("notifications", () => {
  it("supports warning tone and manual dismissal", async () => { const user = userEvent.setup(); render(<ToastProvider><Trigger /></ToastProvider>); await user.click(screen.getByText("Warning")); expect(screen.getByRole("status")).toHaveTextContent("Review warning"); await user.click(screen.getByRole("button", { name: "Dismiss notification" })); expect(screen.queryByText("Review warning")).not.toBeInTheDocument(); });
});
