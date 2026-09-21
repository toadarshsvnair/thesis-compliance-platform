"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireSession } from "@/lib/use-session";
import { hasRole, ROLE_LABELS } from "@/lib/session";
import {
  ApiError,
  AdminUser,
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  listUniversities,
  resetAdminUserPassword,
  updateAdminUser,
} from "@/lib/api";
import type { Role, University } from "@/lib/types";
import { Button, Masthead, Panel, SectionHeading, StatusBadge } from "@/components/ui";

const ROLE_ORDER: Role[] = ["student", "research_officer", "university_admin", "super_admin"];

export default function AdminUsersPage() {
  const session = useRequireSession();
  const router = useRouter();

  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [universities, setUniversities] = useState<University[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const refresh = useCallback(() => {
    if (!session) return;
    listAdminUsers(session)
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load users."));
  }, [session]);

  useEffect(refresh, [refresh]);
  useEffect(() => {
    if (session) listUniversities(session).then(setUniversities);
  }, [session]);

  if (!session) return null;
  if (!hasRole(session, "university_admin", "super_admin")) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-brick text-sm">This page requires a University Admin or Super Admin role.</p>
        <Button variant="ghost" onClick={() => router.push("/dashboard")} className="mt-4 !px-0">
          ← Back to dashboard
        </Button>
      </main>
    );
  }

  async function handleSuspendToggle(user: AdminUser) {
    if (!session) return;
    try {
      await updateAdminUser(session, user.id, { active: !user.active });
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed.");
    }
  }

  async function handleResetPassword(user: AdminUser) {
    if (!session) return;
    const newPassword = prompt(`New password for ${user.email} (min. 8 characters):`);
    if (!newPassword) return;
    try {
      await resetAdminUserPassword(session, user.id, newPassword);
      alert(`Password reset for ${user.email}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Password reset failed.");
    }
  }

  async function handleDelete(user: AdminUser) {
    if (!session) return;
    if (!confirm(`Permanently delete ${user.email}? This cannot be undone.`)) return;
    try {
      await deleteAdminUser(session, user.id);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed. If this account owns submissions, suspend it instead.");
    }
  }

  async function handleEditExpiry(user: AdminUser) {
    if (!session) return;
    const input = prompt(
      `Account end date for ${user.email} (YYYY-MM-DD), or leave blank to remove any end date:`,
      user.expires_at ? user.expires_at.slice(0, 10) : ""
    );
    if (input === null) return;
    try {
      if (input.trim() === "") {
        await updateAdminUser(session, user.id, { clearExpiry: true });
      } else {
        await updateAdminUser(session, user.id, { expiresAt: new Date(input).toISOString() });
      }
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed.");
    }
  }

  return (
    <>
      <Masthead subtitle="User management" />
      <main className="max-w-5xl mx-auto px-6 py-10">
        <Button variant="ghost" onClick={() => router.push("/dashboard")} className="mb-6 !px-0">
          ← Back to dashboard
        </Button>

        <div className="flex items-center justify-between mb-4">
          <SectionHeading>Accounts</SectionHeading>
        </div>
        <Button onClick={() => setShowCreate((v) => !v)} className="mb-6">
          {showCreate ? "Cancel" : "+ Create user"}
        </Button>

        {error && <p className="text-sm text-brick mb-4">{error}</p>}

        {showCreate && (
          <CreateUserForm
            session={session}
            universities={universities}
            onCreated={() => {
              setShowCreate(false);
              refresh();
            }}
          />
        )}

        {users === null && !error && <p className="text-sm text-muted">Loading…</p>}
        {users && users.length === 0 && <p className="text-sm text-muted">No accounts yet.</p>}
        {users && users.length > 0 && (
          <Panel>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Role(s)</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">End date</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const expired = u.expires_at && new Date(u.expires_at) < new Date();
                  return (
                    <tr key={u.id} className="border-b border-line last:border-0 align-top">
                      <td className="px-4 py-3">{u.display_name || "—"}</td>
                      <td className="px-4 py-3 text-muted">{u.email}</td>
                      <td className="px-4 py-3">
                        {u.roles.map((r) => ROLE_LABELS[r.role as Role] ?? r.role).join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3">
                        {!u.active ? (
                          <StatusBadge status="rejected" />
                        ) : expired ? (
                          <span className="inline-block rounded-sm border border-ochre/50 text-ochre bg-ochre/10 px-2 py-0.5 text-xs font-medium">
                            Expired
                          </span>
                        ) : (
                          <StatusBadge status="fixed" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted">
                        {u.expires_at ? new Date(u.expires_at).toLocaleDateString() : "No end date"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          <Button variant="ghost" onClick={() => handleSuspendToggle(u)}>
                            {u.active ? "Suspend" : "Reactivate"}
                          </Button>
                          <Button variant="ghost" onClick={() => handleResetPassword(u)}>
                            Reset password
                          </Button>
                          <Button variant="ghost" onClick={() => handleEditExpiry(u)}>
                            Set end date
                          </Button>
                          <Button variant="ghost" className="!text-brick" onClick={() => handleDelete(u)}>
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Panel>
        )}
      </main>
    </>
  );
}

function CreateUserForm({
  session,
  universities,
  onCreated,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  universities: University[];
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("research_officer");
  const [universityId, setUniversityId] = useState<number | "">(universities[0]?.id ?? "");
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!universityId) {
      setError("Select a university.");
      return;
    }
    setBusy(true);
    try {
      await createAdminUser(session, {
        email,
        password,
        displayName,
        role,
        universityId,
        expiresAt: expiresAt ? new Date(expiresAt).toISOString() : undefined,
      });
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="p-5 mb-8">
      <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Full name">
          <input required value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm" />
        </Field>
        <Field label="Email">
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm" />
        </Field>
        <Field label="Temporary password (min. 8 characters)">
          <input required minLength={8} type="text" value={password} onChange={(e) => setPassword(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm" />
        </Field>
        <Field label="University">
          <select value={universityId} onChange={(e) => setUniversityId(Number(e.target.value))} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm">
            {universities.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Role">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm">
            {ROLE_ORDER.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </Field>
        <Field label="Account end date (optional)">
          <input type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm" />
        </Field>
        {error && <p className="text-sm text-brick sm:col-span-2">{error}</p>}
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}</Button>
        </div>
      </form>
    </Panel>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-ink mb-1.5">{label}</span>
      {children}
    </label>
  );
}
