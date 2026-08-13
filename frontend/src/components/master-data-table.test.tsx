import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MasterDataTable } from "@/components/master-data-table";

const rows = [
  { id: "2", department_code: "EEE", department_name: "Electrical", is_active: true },
  { id: "1", department_code: "CSE", department_name: "Computer Science", is_active: false },
];
const columns = [{ key: "department_code", label: "Department Code" }, { key: "department_name", label: "Department Name" }, { key: "is_active", label: "Status" }];
const base = { rows, columns, lookups: {}, selected: new Set<string>(), onSelection: vi.fn(), sortKey: "department_code", sortDirection: "asc" as const, onSort: vi.fn(), onView: vi.fn(), onEdit: vi.fn(), onDuplicate: vi.fn(), onDelete: vi.fn(), onRestore: vi.fn() };

describe("master-data table", () => {
  it("does not render record or relationship UUIDs in the primary table", () => {
    const recordId = "d053cef9-62d5-4fdd-b11d-bc1cf4520827";
    const departmentId = "5ee3ecfd-694b-43aa-9c2d-3fc52d1a0ad1";
    render(<MasterDataTable {...base} rows={[{ id: recordId, faculty_code: "VCE042", full_name: "Dr. R. Kumar", department_id: departmentId }]} columns={[{ key: "id", label: "ID" }, { key: "faculty_code", label: "Faculty code" }, { key: "full_name", label: "Full name" }, { key: "department_id", label: "Department", lookup: { endpoint: "/departments", labelKeys: ["department_name"] } }]} lookups={{ "/departments": new Map([[departmentId, "Computer Science & Engineering"]]) }} canManage={false} />);
    expect(screen.getByText("VCE042")).toBeInTheDocument();
    expect(screen.getByText("Computer Science & Engineering")).toBeInTheDocument();
    expect(screen.queryByText(recordId)).not.toBeInTheDocument();
    expect(screen.queryByText(departmentId)).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "ID" })).not.toBeInTheDocument();
  });

  it("supports sorting, column hiding, resizing, and selection", async () => {
    const user = userEvent.setup();
    render(<MasterDataTable {...base} canManage />);
    await user.click(screen.getByRole("button", { name: "Department Code ↑" }));
    expect(base.onSort).toHaveBeenCalledWith("department_code");
    await user.click(screen.getByText("Columns"));
    await user.click(screen.getByLabelText("Department Name"));
    expect(screen.queryByRole("columnheader", { name: "Department Name" })).not.toBeInTheDocument();
    fireEvent.pointerDown(screen.getByRole("button", { name: "Resize Department Code column" }), { clientX: 100 });
    fireEvent.pointerMove(window, { clientX: 140 });
    fireEvent.pointerUp(window);
    await user.click(screen.getByLabelText("Select all visible rows"));
    expect(base.onSelection).toHaveBeenCalledWith(new Set(["2", "1"]));
  });

  it("hides every mutation action from read-only users", () => {
    render(<MasterDataTable {...base} canManage={false} />);
    expect(screen.getAllByRole("button", { name: "View details" })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Duplicate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restore" })).not.toBeInTheDocument();
  });
});
