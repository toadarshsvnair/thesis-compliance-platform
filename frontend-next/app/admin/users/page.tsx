"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireSession } from "@/lib/use-session";
import { clearSession, hasRole, ROLE_LABELS } from "@/lib/session";
import {
  ApiError,
  AdminUser,
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  listFaculties,
  listUniversities,
  resetAdminUserPassword,
  updateAdminUser,
} from "@/lib/api";
import type { Faculty, Role, University } from "@/lib/types";
import { Button, AppShell, Modal, Panel, SectionHeading } from "@/components/ui";

const ROLE_ORDER: Role[] = ["student", "research_officer", "university_admin", "super_admin"];

export default function AdminUsersPage() {
  const session = useRequireSession();
  const router = useRouter();

  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [universities, setUniversities] = useState<University[]>([]);
  const [faculties, setFaculties] = useState<Faculty[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [resettingUser, setResettingUser] = useState<AdminUser | null>(null);
  const [deletingUser, setDeletingUser] = useState<AdminUser | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  const refresh = useCallback(() => {
    if (!session) return;
    listAdminUsers(session)
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load users."));
  }, [session]);

  useEffect(refresh, [refresh]);
  useEffect(() => {
    if (!session) return;
    listUniversities(session).then((rows) => {
      setUniversities(rows);
      if (rows.length > 0) listFaculties(session, rows[0].id).then(setFaculties);
    });
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

  function flashNotice(msg: string) {
    setNotice(msg);
    setTimeout(() => setNotice((n) => (n === msg ? null : n)), 3500);
  }

  async function handleSuspendToggle(user: AdminUser) {
    if (!session) return;
    setOpenMenuId(null);
    try {
      await updateAdminUser(session, user.id, { active: !user.active });
      flashNotice(user.active ? `${user.email} suspended.` : `${user.email} reactivated.`);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed.");
    }
  }

  async function handleDelete() {
    if (!session || !deletingUser) return;
    try {
      await deleteAdminUser(session, deletingUser.id);
      flashNotice(`${deletingUser.email} deleted.`);
      setDeletingUser(null);
      refresh();
    } catch (e) {
      // If this isn't an ApiError, the request never completed as a normal
      // HTTP response (a network failure, a CORS issue, etc.) -- show
      // whatever the real error actually says rather than guessing at a
      // generic message that may have nothing to do with the true cause.
      const message = e instanceof ApiError
        ? e.message
        : e instanceof Error
        ? `Delete failed: ${e.message}`
        : "Delete failed for an unknown reason.";
      setError(message);
      setDeletingUser(null);
    }
  }

  return (
    <AppShell
      active="/admin/users"
      isAdmin={hasRole(session, "university_admin", "super_admin")}
      userLabel={session.displayName || session.email}
      roleLabel={session.roles.map((r) => ROLE_LABELS[r]).join(", ")}
      onSignOut={() => {
        clearSession();
        router.replace("/login");
      }}
      onNavigate={(href) => router.push(href)}
    >
      <main className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="font-serif text-2xl text-ink mb-8">Manage users</h1>

        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <SectionHeading>Accounts</SectionHeading>
          <Button onClick={() => setShowCreate(true)}>+ Create user</Button>
        </div>

        {notice && (
          <div className="mb-4 text-sm text-forest bg-forest/10 border border-forest/30 rounded px-3 py-2">
            {notice}
          </div>
        )}
        {error && <p className="text-sm text-brick mb-4">{error}</p>}

        {users === null && !error && <p className="text-sm text-muted">Loading…</p>}
        {users && users.length === 0 && (
          <Panel className="p-6 text-center">
            <p className="text-sm text-muted">No accounts yet.</p>
          </Panel>
        )}
        {users && users.length > 0 && (
          <Panel className="overflow-visible">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-medium text-muted">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Role(s)</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">End date</th>
                  <th className="px-4 py-3 font-medium w-16"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const expired = !!u.expires_at && new Date(u.expires_at) < new Date();
                  return (
                    <tr key={u.id} className="border-b border-line last:border-0 align-top hover:bg-paper/60">
                      <td className="px-4 py-3">{u.display_name || "—"}</td>
                      <td className="px-4 py-3 text-muted">{u.email}</td>
                      <td className="px-4 py-3">
                        {u.roles.map((r) => ROLE_LABELS[r.role as Role] ?? r.role).join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3">
                        {!u.active ? (
                          <span className="inline-block rounded-sm border border-brick/40 text-brick bg-brick/5 px-2 py-0.5 text-xs font-medium">
                            Suspended
                          </span>
                        ) : expired ? (
                          <span className="inline-block rounded-sm border border-ochre/50 text-ochre bg-ochre/10 px-2 py-0.5 text-xs font-medium">
                            Expired
                          </span>
                        ) : (
                          <span className="inline-block rounded-sm border border-forest/40 text-forest bg-forest/5 px-2 py-0.5 text-xs font-medium">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted">
                        {u.expires_at ? new Date(u.expires_at).toLocaleDateString() : "No end date"}
                      </td>
                      <td className="px-4 py-3 text-right relative">
                        <RowActionMenu
                          open={openMenuId === u.id}
                          onToggle={() => setOpenMenuId(openMenuId === u.id ? null : u.id)}
                          onClose={() => setOpenMenuId(null)}
                          user={u}
                          onEdit={() => {
                            setOpenMenuId(null);
                            setEditingUser(u);
                          }}
                          onResetPassword={() => {
                            setOpenMenuId(null);
                            setResettingUser(u);
                          }}
                          onSuspendToggle={() => handleSuspendToggle(u)}
                          onDelete={() => {
                            setOpenMenuId(null);
                            setDeletingUser(u);
                          }}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Panel>
        )}
      </main>

      {showCreate && (
        <CreateUserModal
          session={session}
          universities={universities}
          faculties={faculties}
          onFacultiesForUniversity={(uid) => listFaculties(session, uid).then(setFaculties)}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            flashNotice("Account created.");
            refresh();
          }}
        />
      )}

      {editingUser && (
        <EditUserModal
          session={session}
          user={editingUser}
          faculties={faculties}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            setEditingUser(null);
            flashNotice("Account updated.");
            refresh();
          }}
        />
      )}

      {resettingUser && (
        <ResetPasswordModal
          session={session}
          user={resettingUser}
          onClose={() => setResettingUser(null)}
          onDone={() => {
            setResettingUser(null);
            flashNotice(`Password reset for ${resettingUser.email}.`);
          }}
        />
      )}

      {deletingUser && (
        <Modal
          title="Delete account?"
          onClose={() => setDeletingUser(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeletingUser(null)}>Cancel</Button>
              <Button variant="danger" onClick={handleDelete}>Delete permanently</Button>
            </>
          }
        >
          <p className="text-sm text-ink">
            Permanently delete <strong>{deletingUser.email}</strong>? This cannot be undone.
          </p>
          <p className="text-sm text-muted mt-2">
            If this account owns any submissions, deletion will be blocked — suspend it instead to preserve audit history.
          </p>
        </Modal>
      )}
    </AppShell>
  );
}

function RowActionMenu({
  open,
  onToggle,
  onClose,
  user,
  onEdit,
  onResetPassword,
  onSuspendToggle,
  onDelete,
}: {
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  user: AdminUser;
  onEdit: () => void;
  onResetPassword: () => void;
  onSuspendToggle: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open, onClose]);

  return (
    <div ref={ref} className="inline-block text-left">
      <button
        onClick={onToggle}
        className="focus-ring w-8 h-8 rounded hover:bg-paper border border-transparent hover:border-line text-muted text-lg leading-none"
        aria-label="Actions"
        aria-haspopup="menu"
      >
        ⋯
      </button>
      {open && (
        <div className="absolute right-4 mt-1 w-44 bg-panel border border-line rounded-md shadow-lg z-40 py-1 text-left">
          <button onClick={onEdit} className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper">
            Edit details
          </button>
          <button onClick={onResetPassword} className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper">
            Reset password
          </button>
          <button onClick={onSuspendToggle} className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper">
            {user.active ? "Suspend" : "Reactivate"}
          </button>
          <div className="border-t border-line my-1" />
          <button onClick={onDelete} className="w-full text-left px-3 py-2 text-sm text-brick hover:bg-brick/5">
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function CreateUserModal({
  session,
  universities,
  faculties,
  onFacultiesForUniversity,
  onClose,
  onCreated,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  universities: University[];
  faculties: Faculty[];
  onFacultiesForUniversity: (universityId: number) => void;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [universityId, setUniversityId] = useState<number | "">(universities[0]?.id ?? "");
  const [programme, setProgramme] = useState("");
  const [facultyId, setFacultyId] = useState<number | "">("");
  const [registrationNumber, setRegistrationNumber] = useState("");
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
        programme: programme || undefined,
        facultyId: facultyId || undefined,
        registrationNumber: registrationNumber || undefined,
      });
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Create user"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Creating…" : "Create account"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Full name">
          <input required value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        <Field label="Email">
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        <Field label="Temporary password (min. 8 characters)">
          <input required minLength={8} type="text" value={password} onChange={(e) => setPassword(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        <Field label="University">
          <select
            value={universityId}
            onChange={(e) => {
              const id = Number(e.target.value);
              setUniversityId(id);
              onFacultiesForUniversity(id);
            }}
            className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded"
          >
            {universities.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Role">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {ROLE_ORDER.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </Field>
        {role === "student" && (
          <>
            <Field label="Registration number (optional)">
              <input value={registrationNumber} onChange={(e) => setRegistrationNumber(e.target.value)} placeholder="e.g. PHD2024-0042" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
            </Field>
            <Field label="Programme (optional)">
              <input value={programme} onChange={(e) => setProgramme(e.target.value)} placeholder="e.g. PhD Computer Science" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
            </Field>
            <Field label="Faculty (optional)">
              <select value={facultyId} onChange={(e) => setFacultyId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
                <option value="">—</option>
                {faculties.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </Field>
          </>
        )}
        <Field label="Account end date (optional)">
          <input type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

function EditUserModal({
  session,
  user,
  faculties,
  onClose,
  onSaved,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  user: AdminUser;
  faculties: Faculty[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [displayName, setDisplayName] = useState(user.display_name ?? "");
  const [programme, setProgramme] = useState(user.programme ?? "");
  const [facultyId, setFacultyId] = useState<number | "">(user.faculty_id ?? "");
  const [registrationNumber, setRegistrationNumber] = useState(user.registration_number ?? "");
  const [expiresAt, setExpiresAt] = useState(user.expires_at ? user.expires_at.slice(0, 10) : "");
  const originalRole = (user.roles[0]?.role as Role) ?? "student";
  const [role, setRole] = useState<Role>(originalRole);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isStudent = role === "student";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateAdminUser(session, user.id, {
        displayName,
        programme: programme || undefined,
        facultyId: facultyId || undefined,
        clearFaculty: facultyId === "",
        registrationNumber: registrationNumber || undefined,
        expiresAt: expiresAt ? new Date(expiresAt).toISOString() : undefined,
        clearExpiry: expiresAt === "",
        // Only sent when actually changed -- the backend treats any
        // provided role as an intentional change (and applies the same
        // self-role-change / last-super-admin safety checks used at
        // creation), so sending the unchanged value on every edit would
        // wrongly trip those checks for an admin editing their own other
        // details.
        role: role !== originalRole ? role : undefined,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Edit ${user.email}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Saving…" : "Save changes"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Full name">
          <input required value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        <Field label="Role">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {ROLE_ORDER.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </Field>
        {isStudent && (
          <>
            <Field label="Registration number">
              <input value={registrationNumber} onChange={(e) => setRegistrationNumber(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
            </Field>
            <Field label="Programme">
              <input value={programme} onChange={(e) => setProgramme(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
            </Field>
            <Field label="Faculty">
              <select value={facultyId} onChange={(e) => setFacultyId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
                <option value="">—</option>
                {faculties.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </Field>
          </>
        )}
        <Field label="Account end date">
          <input type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
          <p className="text-xs text-muted mt-1">Leave blank for no end date.</p>
        </Field>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

function ResetPasswordModal({
  session,
  user,
  onClose,
  onDone,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  user: AdminUser;
  onClose: () => void;
  onDone: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await resetAdminUserPassword(session, user.id, newPassword);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Password reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Reset password`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy || newPassword.length < 8}>{busy ? "Saving…" : "Set new password"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-muted">Setting a new password for <strong>{user.email}</strong>.</p>
        <Field label="New password (min. 8 characters)">
          <input required minLength={8} type="text" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </Field>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
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
