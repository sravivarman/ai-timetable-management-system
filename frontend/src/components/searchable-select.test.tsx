import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SearchableSelect } from "@/components/searchable-select";

describe("SearchableSelect", () => {
  it("filters readable labels and returns the hidden ID", async () => { const change = vi.fn(); const user = userEvent.setup(); render(<SearchableSelect label="Faculty" value="" options={[{ value: "faculty-1", label: "VCE001 · Anitha Rao" }, { value: "faculty-2", label: "VCE002 · Bala Kumar" }]} onChange={change} />); const input = screen.getByRole("combobox", { name: "Faculty" }); await user.click(input); await user.type(input, "Anitha"); expect(screen.queryByText("VCE002 · Bala Kumar")).not.toBeInTheDocument(); await user.click(screen.getByRole("option", { name: /VCE001/i })); expect(change).toHaveBeenCalledWith("faculty-1"); });
  it("exposes loading and permission errors accessibly", () => { const { rerender } = render(<SearchableSelect label="Classroom" value="" options={[]} onChange={vi.fn()} loading />); expect(screen.getByPlaceholderText("Loading classroom…")).toBeDisabled(); rerender(<SearchableSelect label="Classroom" value="" options={[]} onChange={vi.fn()} error="Options unavailable: Forbidden" />); expect(screen.getByRole("alert")).toHaveTextContent("Forbidden"); });
});
