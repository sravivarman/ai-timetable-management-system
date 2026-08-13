"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Power, Trash2, UserPlus } from "lucide-react";
import { useMemo, useState } from "react";
import { Card, EmptyState, ErrorState, LoadingState, Modal, PageHeader, StatusBadge } from "@/components/ui";
import { usersAdminApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { Role, User } from "@/lib/types";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/providers/toast-provider";

const approvedRoles = new Set(["Administrator", "Principal", "Dean", "Timetable Coordinator"]);
const roleLabel = (name: string) => name === "Dean" ? "Dean Academics" : name;

export default function UsersPage() {
  const client = useQueryClient();
  const { hasRole } = useAuth();
  const isAdministrator = hasRole("Administrator", "System Administrator");
  const { notify } = useToast();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [editor, setEditor] = useState<{ mode: "create" | "edit"; id?: string } | null>(null);
  const users = useQuery({ queryKey: queryKeys.users, queryFn: usersAdminApi.list, enabled: isAdministrator, retry: false });
  const roles = useQuery({ queryKey: queryKeys.roles, queryFn: usersAdminApi.roles, enabled: isAdministrator, retry: false });
  const options = useMemo(() => (roles.data ?? []).filter((item) => approvedRoles.has(item.name)), [roles.data]);
  const rows = useMemo(() => (users.data ?? []).filter((item) => {
    const needle = search.toLowerCase();
    return (!needle || `${item.full_name} ${item.email}`.toLowerCase().includes(needle)) && (!role || item.roles.some((itemRole) => itemRole.id === role)) && (!status || String(item.is_active) === status);
  }), [users.data, search, role, status]);
  const refresh = () => client.invalidateQueries({ queryKey: queryKeys.users });
  const stateMutation = useMutation({ mutationFn: (user: User) => usersAdminApi.update(user.id, { is_active: !user.is_active }), onSuccess: (updated) => { notify(updated.is_active ? "Login account activated." : "Login account deactivated."); void refresh(); }, onError: (error) => notify(apiErrorMessage(error), "error") });
  const remove = useMutation({ mutationFn: (userId: string) => usersAdminApi.remove(userId), onSuccess: () => { notify("Login account deleted."); void refresh(); }, onError: (error) => notify(apiErrorMessage(error), "error") });

  if (!isAdministrator) return <><PageHeader title="Users" description="Login account administration is restricted to System Administrators." /><Card><ErrorState message="You do not have permission to manage login accounts." /></Card></>;

  return <><PageHeader title="Users" description="Manage the approved institutional login accounts. Faculty and students do not require accounts." actions={<button className="button-primary gap-2" onClick={() => setEditor({ mode: "create" })}><UserPlus className="h-4 w-4" />Create login account</button>} />
    <Card><div className="mb-4 grid gap-3 md:grid-cols-4"><label><span className="label">Search</span><input className="field" aria-label="Search users" placeholder="Name or email…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><label><span className="label">Role</span><select className="field" aria-label="Role filter" value={role} onChange={(event) => setRole(event.target.value)}><option value="">All approved roles</option>{options.map((item) => <option key={item.id} value={item.id}>{roleLabel(item.name)}</option>)}</select></label><label><span className="label">Status</span><select className="field" aria-label="User status filter" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="true">Active</option><option value="false">Inactive</option></select></label><button className="button-secondary self-end" onClick={() => { setSearch(""); setRole(""); setStatus(""); }}>Clear filters</button></div>
      {users.isLoading || roles.isLoading ? <LoadingState /> : users.isError || roles.isError ? <ErrorState message={apiErrorMessage(users.error ?? roles.error)} retry={() => { void users.refetch(); void roles.refetch(); }} /> : !rows.length ? <EmptyState title="No login accounts found" detail="Only Administrator, Principal, Dean Academics, and Timetable Coordinator accounts belong here." /> : <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Name", "Email", "Role", "Status", "Actions"].map((heading) => <th key={heading} className="px-3 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y">{rows.map((user) => <tr key={user.id}><td className="px-3 py-3 font-medium">{user.full_name}</td><td className="px-3 py-3">{user.email}</td><td className="px-3 py-3">{user.roles.filter((item) => approvedRoles.has(item.name)).map((item) => roleLabel(item.name)).join(", ") || "Unsupported legacy role"}</td><td className="px-3 py-3"><StatusBadge value={user.is_active ? "ACTIVE" : "INACTIVE"} /></td><td className="px-3 py-3"><div className="flex gap-1"><button className="rounded p-2 text-slate-600 hover:bg-slate-100" aria-label={`Edit ${user.full_name}`} onClick={() => setEditor({ mode: "edit", id: user.id })}><Pencil className="h-4 w-4" /></button><button className="rounded p-2 text-amber-700 hover:bg-amber-50" aria-label={`${user.is_active ? "Deactivate" : "Activate"} ${user.full_name}`} disabled={stateMutation.isPending} onClick={() => { if (window.confirm(`${user.is_active ? "Deactivate" : "Activate"} this login account?`)) stateMutation.mutate(user); }}><Power className="h-4 w-4" /></button><button className="rounded p-2 text-red-700 hover:bg-red-50" aria-label={`Delete ${user.full_name}`} disabled={remove.isPending} onClick={() => { if (window.confirm("Delete this login account? This cannot be undone.")) remove.mutate(user.id); }}><Trash2 className="h-4 w-4" /></button></div></td></tr>)}</tbody></table></div>}
    </Card>{editor && <UserDialog mode={editor.mode} userId={editor.id} roles={options} onClose={() => setEditor(null)} onSaved={() => { setEditor(null); void refresh(); }} />}</>;
}

function UserDialog({ mode, userId, roles, onClose, onSaved }: { mode: "create" | "edit"; userId?: string; roles: Role[]; onClose(): void; onSaved(): void }) {
  const { notify } = useToast();
  const detail = useQuery({ queryKey: queryKeys.user(userId ?? "new"), queryFn: () => usersAdminApi.get(userId!), enabled: mode === "edit" && Boolean(userId), retry: false });
  if (detail.isLoading) return <Modal title="Edit login account" onClose={onClose}><LoadingState /></Modal>;
  if (detail.isError) return <Modal title="Edit login account" onClose={onClose}><ErrorState message={apiErrorMessage(detail.error)} /></Modal>;
  return <UserForm key={detail.data?.id ?? "new"} mode={mode} user={detail.data} roles={roles} onClose={onClose} onSaved={onSaved} notify={notify} />;
}

function UserForm({ mode, user, roles, onClose, onSaved, notify }: { mode: "create" | "edit"; user?: User; roles: Role[]; onClose(): void; onSaved(): void; notify(message: string, tone?: "success" | "warning" | "error" | "info"): void }) {
  const [email, setEmail] = useState(user?.email ?? ""); const [name, setName] = useState(user?.full_name ?? ""); const [password, setPassword] = useState(""); const [roleId, setRoleId] = useState(user?.roles.find((item) => approvedRoles.has(item.name))?.id ?? "");
  const mutation = useMutation({ mutationFn: () => { if (!roleId) throw new Error("Select an approved login role"); if (mode === "create") return usersAdminApi.create({ email: email.trim(), full_name: name.trim(), password, role_ids: [roleId] }); const payload: { email: string; full_name: string; role_ids: string[]; password?: string } = { email: email.trim(), full_name: name.trim(), role_ids: [roleId] }; if (password) payload.password = password; return usersAdminApi.update(user!.id, payload); }, onSuccess: () => { notify(mode === "create" ? "Login account created." : "Login account updated."); onSaved(); }, onError: (error) => notify(apiErrorMessage(error), "error") });
  const invalid = !email.trim() || !name.trim() || !roleId || (mode === "create" && password.length < 12) || (Boolean(password) && password.length < 12);
  return <Modal title={mode === "create" ? "Create login account" : "Edit login account"} onClose={onClose} footer={<><button className="button-secondary" onClick={onClose}>Cancel</button><button className="button-primary" disabled={invalid || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Saving…" : "Save account"}</button></>}><div className="space-y-4"><label><span className="label">Full name</span><input className="field" aria-label="Full name" value={name} onChange={(event) => setName(event.target.value)} /></label><label><span className="label">Email</span><input className="field" aria-label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><label><span className="label">Approved login role</span><select className="field" aria-label="Approved login role" value={roleId} onChange={(event) => setRoleId(event.target.value)}><option value="">Select role</option>{roles.map((role) => <option key={role.id} value={role.id}>{roleLabel(role.name)}</option>)}</select></label><label><span className="label">{mode === "create" ? "Password" : "Reset password (optional)"}</span><input className="field" aria-label={mode === "create" ? "Password" : "Reset password"} type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} /><span className="mt-1 block text-xs text-slate-500">Minimum 12 characters. Changing it invalidates existing sessions.</span></label></div></Modal>;
}
