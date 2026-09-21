"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireSession } from "@/lib/use-session";
import { clearSession, hasRole, ROLE_LABELS } from "@/lib/session";
import {
  ApiError,
  RuleSetSummary,
  RuleRow,
  addRule,
  bulkUploadRules,
  cloneRuleSet,
  createRuleSet,
  deleteRuleSet,
  downloadFile,
  listFaculties,
  listDocumentTypes,
  listRuleSets,
  listRulesInSet,
  listUniversities,
  publishRuleSet,
  retireRuleSet,
  sampleTemplateUrl,
  submitRuleSetForReview,
  updateRule,
  updateRuleSet,
} from "@/lib/api";
import type { DocumentType, Faculty, University } from "@/lib/types";
import { AppShell, Button, Modal, Panel, SectionHeading, StatusBadge } from "@/components/ui";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  retired: "Retired",
};

export default function AdminRulesPage() {
  const session = useRequireSession();
  const router = useRouter();

  const [universities, setUniversities] = useState<University[]>([]);
  const [universityId, setUniversityId] = useState<number | null>(null);
  const [faculties, setFaculties] = useState<Faculty[]>([]);
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [ruleSets, setRuleSets] = useState<RuleSetSummary[] | null>(null);
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null);
  const [rules, setRules] = useState<RuleRow[] | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreateSet, setShowCreateSet] = useState(false);
  const [showAddRule, setShowAddRule] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [editingRule, setEditingRule] = useState<RuleRow | null>(null);
  const [showClone, setShowClone] = useState(false);
  const [editingSet, setEditingSet] = useState<RuleSetSummary | null>(null);
  const [deletingSet, setDeletingSet] = useState<RuleSetSummary | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const refreshRuleSets = useCallback(() => {
    if (!session || !universityId) return;
    listRuleSets(session, universityId)
      .then(setRuleSets)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load rule sets."));
  }, [session, universityId]);

  const refreshRules = useCallback(() => {
    if (!session || !selectedSetId) return;
    listRulesInSet(session, selectedSetId)
      .then(setRules)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load rules."));
  }, [session, selectedSetId]);

  useEffect(() => {
    if (!session) return;
    listUniversities(session).then((rows) => {
      setUniversities(rows);
      if (rows.length > 0) setUniversityId(rows[0].id);
    });
  }, [session]);

  useEffect(refreshRuleSets, [refreshRuleSets]);
  useEffect(() => {
    if (!session || !universityId) return;
    listFaculties(session, universityId).then(setFaculties);
    listDocumentTypes(session, universityId).then(setDocumentTypes);
  }, [session, universityId]);
  useEffect(refreshRules, [refreshRules]);

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

  async function handleDeleteRuleSet() {
    if (!session || !deletingSet) return;
    setDeleteBusy(true);
    try {
      await deleteRuleSet(session, deletingSet.id);
      setDeletingSet(null);
      if (selectedSetId === deletingSet.id) setSelectedSetId(null);
      flashNotice("Rule set deleted.");
      refreshRuleSets();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete this rule set.");
    } finally {
      setDeleteBusy(false);
    }
  }

  const selectedSet = ruleSets?.find((rs) => rs.id === selectedSetId) ?? null;
  const isDraft = selectedSet?.status === "draft";

  async function handleLifecycleAction(action: "submit-review" | "publish" | "retire") {
    if (!session || !selectedSetId) return;
    const comment = prompt(
      action === "submit-review" ? "Comment for submitting this rule set for review:" :
      action === "publish" ? "Comment for publishing this rule set:" :
      "Comment for retiring this rule set:"
    );
    if (!comment || comment.trim().length < 3) {
      setError("A comment (at least 3 characters) is required for this action.");
      return;
    }
    try {
      if (action === "submit-review") await submitRuleSetForReview(session, selectedSetId, comment);
      else if (action === "publish") await publishRuleSet(session, selectedSetId, comment);
      else await retireRuleSet(session, selectedSetId, comment);
      flashNotice("Done.");
      refreshRuleSets();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    }
  }

  return (
    <AppShell
      active="/admin/rules"
      isAdmin={hasRole(session, "university_admin", "super_admin")}
      userLabel={session.displayName || session.email}
      roleLabel={session.roles.map((r) => ROLE_LABELS[r]).join(", ")}
      onSignOut={() => {
        clearSession();
        router.replace("/login");
      }}
      onNavigate={(href) => router.push(href)}
    >
      <main className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="font-serif text-2xl text-ink mb-8">Rule management</h1>

        {notice && (
          <div className="mb-4 text-sm text-forest bg-forest/10 border border-forest/30 rounded px-3 py-2">{notice}</div>
        )}
        {error && <p className="text-sm text-brick mb-4">{error}</p>}

        {universities.length > 1 && (
          <div className="mb-6 max-w-xs">
            <label className="block text-sm font-medium text-ink mb-1.5">University</label>
            <select
              className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              value={universityId ?? ""}
              onChange={(e) => {
                setUniversityId(Number(e.target.value));
                setSelectedSetId(null);
              }}
            >
              {universities.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-8">
          <section>
            <div className="flex items-center justify-between mb-4">
              <SectionHeading>Rule sets</SectionHeading>
            </div>
            <Button onClick={() => setShowCreateSet(true)} className="w-full mb-4">+ New rule set</Button>
            {ruleSets === null && <p className="text-sm text-muted">Loading…</p>}
            {ruleSets && ruleSets.length === 0 && <p className="text-sm text-muted">No rule sets yet.</p>}
            <div className="space-y-2">
              {ruleSets?.map((rs) => (
                <div
                  key={rs.id}
                  onClick={() => setSelectedSetId(rs.id)}
                  className={`w-full text-left px-3 py-2.5 rounded border text-sm transition-colors cursor-pointer ${
                    selectedSetId === rs.id ? "border-navy bg-navy/5" : "border-line hover:border-navy/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink">{rs.name}</span>
                    <StatusBadge status={rs.status} />
                  </div>
                  <p className="text-xs text-muted mt-0.5">v{rs.version} · {STATUS_LABEL[rs.status] ?? rs.status}</p>
                  <p className="text-xs text-muted mt-0.5">
                    Created {new Date(rs.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}
                  </p>
                  {rs.status === "draft" && (
                    <div className="flex gap-3 mt-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingSet(rs);
                        }}
                        className="text-xs text-navy hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingSet(rs);
                        }}
                        className="text-xs text-brick hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (session) downloadFile(session, sampleTemplateUrl(), "rule_set_bulk_upload_template.xlsx");
              }}
              className="block mt-6 text-sm text-navy hover:underline"
            >
              Download sample Excel template
            </a>
          </section>

          <section>
            {!selectedSet && (
              <Panel className="p-6 text-center">
                <p className="text-sm text-muted">Select a rule set on the left, or create a new one.</p>
              </Panel>
            )}
            {selectedSet && (
              <>
                <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                  <div>
                    <h2 className="font-serif text-xl text-ink">{selectedSet.name}</h2>
                    <p className="text-sm text-muted">
                      v{selectedSet.version} · {STATUS_LABEL[selectedSet.status]}
                      {selectedSet.faculty_id && ` · ${faculties.find((f) => f.id === selectedSet.faculty_id)?.name ?? "Faculty"}`}
                      {selectedSet.document_type_id && ` · ${documentTypes.find((d) => d.id === selectedSet.document_type_id)?.name ?? "Document type"}`}
                    </p>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {selectedSet.status === "draft" && (
                      <Button variant="secondary" onClick={() => handleLifecycleAction("submit-review")}>Submit for review</Button>
                    )}
                    {selectedSet.status === "in_review" && (
                      <Button onClick={() => handleLifecycleAction("publish")}>Publish</Button>
                    )}
                    {selectedSet.status === "published" && (
                      <Button variant="danger" onClick={() => handleLifecycleAction("retire")}>Retire</Button>
                    )}
                    <Button variant="ghost" onClick={() => setShowClone(true)}>Clone as new version</Button>
                  </div>
                </div>

                {isDraft && (
                  <div className="flex gap-2 mb-4">
                    <Button variant="secondary" onClick={() => setShowAddRule(true)}>+ Add rule</Button>
                    <Button variant="secondary" onClick={() => setShowBulkUpload(true)}>Upload Excel</Button>
                  </div>
                )}
                {!isDraft && (
                  <p className="text-xs text-muted mb-4">
                    {STATUS_LABEL[selectedSet.status]} rule sets are read-only. Clone this as a new version to make changes.
                  </p>
                )}

                {rules === null && <p className="text-sm text-muted">Loading…</p>}
                {rules && rules.length === 0 && (
                  <Panel className="p-6 text-center">
                    <p className="text-sm text-muted">No rules yet. Add one, or upload an Excel file.</p>
                  </Panel>
                )}
                {rules && rules.length > 0 && (
                  <Panel>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs font-medium text-muted">
                          <th className="px-4 py-3">Rule ID</th>
                          <th className="px-4 py-3">Category</th>
                          <th className="px-4 py-3">Requirement</th>
                          <th className="px-4 py-3">Severity</th>
                          <th className="px-4 py-3">Auto-fix</th>
                          <th className="px-4 py-3">Active</th>
                          {isDraft && <th className="px-4 py-3"></th>}
                        </tr>
                      </thead>
                      <tbody>
                        {rules.map((r) => (
                          <tr key={r.id} className="border-b border-line last:border-0 align-top">
                            <td className="px-4 py-3 font-mono text-xs">{r.rule_id}</td>
                            <td className="px-4 py-3 text-muted">{r.category}</td>
                            <td className="px-4 py-3">{r.requirement}</td>
                            <td className="px-4 py-3">{r.severity}</td>
                            <td className="px-4 py-3 text-muted">{r.auto_fix_allowed ? "Yes" : "No"}</td>
                            <td className="px-4 py-3 text-muted">{r.active ? "Yes" : "No"}</td>
                            {isDraft && (
                              <td className="px-4 py-3">
                                <Button variant="ghost" onClick={() => setEditingRule(r)}>Edit</Button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Panel>
                )}
              </>
            )}
          </section>
        </div>
      </main>

      {showCreateSet && (
        <CreateRuleSetModal
          session={session}
          universityId={universityId}
          faculties={faculties}
          documentTypes={documentTypes}
          onClose={() => setShowCreateSet(false)}
          onCreated={(id) => {
            setShowCreateSet(false);
            flashNotice("Rule set created.");
            refreshRuleSets();
            setSelectedSetId(id);
          }}
        />
      )}
      {showAddRule && selectedSetId && (
        <AddRuleModal
          session={session}
          ruleSetId={selectedSetId}
          onClose={() => setShowAddRule(false)}
          onAdded={() => {
            setShowAddRule(false);
            flashNotice("Rule added.");
            refreshRules();
          }}
        />
      )}
      {showBulkUpload && selectedSetId && (
        <BulkUploadModal
          session={session}
          ruleSetId={selectedSetId}
          onClose={() => setShowBulkUpload(false)}
          onDone={(count) => {
            setShowBulkUpload(false);
            flashNotice(`${count} rule(s) added.`);
            refreshRules();
          }}
        />
      )}
      {editingRule && selectedSetId && (
        <EditRuleModal
          session={session}
          ruleSetId={selectedSetId}
          rule={editingRule}
          onClose={() => setEditingRule(null)}
          onSaved={() => {
            setEditingRule(null);
            flashNotice("Rule updated.");
            refreshRules();
          }}
        />
      )}
      {showClone && selectedSetId && (
        <CloneModal
          session={session}
          ruleSetId={selectedSetId}
          onClose={() => setShowClone(false)}
          onCloned={(id) => {
            setShowClone(false);
            flashNotice("Rule set cloned as a new draft.");
            refreshRuleSets();
            setSelectedSetId(id);
          }}
        />
      )}
      {editingSet && (
        <EditRuleSetModal
          session={session}
          ruleSet={editingSet}
          faculties={faculties}
          documentTypes={documentTypes}
          onClose={() => setEditingSet(null)}
          onSaved={() => {
            setEditingSet(null);
            flashNotice("Rule set updated.");
            refreshRuleSets();
          }}
        />
      )}
      {deletingSet && (
        <Modal
          title="Delete rule set"
          onClose={() => setDeletingSet(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeletingSet(null)}>Cancel</Button>
              <Button variant="danger" onClick={handleDeleteRuleSet} disabled={deleteBusy}>
                {deleteBusy ? "Deleting…" : "Delete permanently"}
              </Button>
            </>
          }
        >
          <p className="text-sm text-ink">
            Delete <strong>{deletingSet.name}</strong> (v{deletingSet.version}) and all of its rules? This can&apos;t be undone.
          </p>
        </Modal>
      )}
    </AppShell>
  );
}

function CreateRuleSetModal({
  session, universityId, faculties, documentTypes, onClose, onCreated,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  universityId: number | null;
  faculties: Faculty[];
  documentTypes: DocumentType[];
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const [version, setVersion] = useState("");
  const [name, setName] = useState("");
  const [facultyId, setFacultyId] = useState<number | "">("");
  const [documentTypeId, setDocumentTypeId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!universityId) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createRuleSet(session, {
        universityId, version, name,
        facultyId: facultyId || undefined,
        documentTypeId: documentTypeId || undefined,
      });
      onCreated(created.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the rule set.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="New rule set"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Creating…" : "Create draft"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Version</span>
          <input required value={version} onChange={(e) => setVersion(e.target.value)} placeholder="e.g. 0.4-draft" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Faculty (optional — leave blank to apply to all)</span>
          <select value={facultyId} onChange={(e) => setFacultyId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            <option value="">—</option>
            {faculties.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Document type (optional)</span>
          <select value={documentTypeId} onChange={(e) => setDocumentTypeId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            <option value="">—</option>
            {documentTypes.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

function EditRuleSetModal({
  session, ruleSet, faculties, documentTypes, onClose, onSaved,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  ruleSet: RuleSetSummary;
  faculties: Faculty[];
  documentTypes: DocumentType[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(ruleSet.name);
  const [facultyId, setFacultyId] = useState<number | "">(ruleSet.faculty_id ?? "");
  const [documentTypeId, setDocumentTypeId] = useState<number | "">(ruleSet.document_type_id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateRuleSet(session, ruleSet.id, {
        name,
        facultyId: facultyId === "" ? null : facultyId,
        documentTypeId: documentTypeId === "" ? null : documentTypeId,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Edit ${ruleSet.name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Saving…" : "Save changes"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-muted">Version (v{ruleSet.version}) can&apos;t be changed here — clone this rule set to start a new version.</p>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Faculty (optional — leave blank to apply to all)</span>
          <select value={facultyId} onChange={(e) => setFacultyId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            <option value="">—</option>
            {faculties.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Document type (optional)</span>
          <select value={documentTypeId} onChange={(e) => setDocumentTypeId(e.target.value ? Number(e.target.value) : "")} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            <option value="">—</option>
            {documentTypes.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

const VALIDATION_METHODS = ["deterministic", "rendered", "pattern-based", "AI-assisted"];
const SEVERITIES = ["Major", "Minor", "Review"];

function AddRuleModal({
  session, ruleSetId, onClose, onAdded,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  ruleSetId: number;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [ruleId, setRuleId] = useState("");
  const [category, setCategory] = useState("");
  const [requirement, setRequirement] = useState("");
  const [validationMethod, setValidationMethod] = useState(VALIDATION_METHODS[0]);
  const [severity, setSeverity] = useState(SEVERITIES[0]);
  const [autoFixAllowed, setAutoFixAllowed] = useState(false);
  const [sourceReference, setSourceReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await addRule(session, ruleSetId, {
        ruleId: ruleId.toUpperCase(), category, requirement, validationMethod, severity,
        autoFixAllowed, sourceReference: sourceReference || undefined,
      });
      onAdded();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add the rule.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Add rule"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Adding…" : "Add rule"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Rule ID</span>
          <input required value={ruleId} onChange={(e) => setRuleId(e.target.value)} placeholder="e.g. PAGE-006" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded font-mono" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Category</span>
          <input required value={category} onChange={(e) => setCategory(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Requirement</span>
          <textarea required value={requirement} onChange={(e) => setRequirement(e.target.value)} rows={3} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Validation method</span>
          <select value={validationMethod} onChange={(e) => setValidationMethod(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {VALIDATION_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Severity</span>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={autoFixAllowed} onChange={(e) => setAutoFixAllowed(e.target.checked)} />
          <span className="text-sm text-ink">Auto-fix allowed</span>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Source reference (optional)</span>
          <input value={sourceReference} onChange={(e) => setSourceReference(e.target.value)} placeholder="e.g. Annexure 19" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

function EditRuleModal({
  session, ruleSetId, rule, onClose, onSaved,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  ruleSetId: number;
  rule: RuleRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState(rule.category);
  const [requirement, setRequirement] = useState(rule.requirement);
  const [validationMethod, setValidationMethod] = useState(rule.validation_method);
  const [severity, setSeverity] = useState(rule.severity);
  const [autoFixAllowed, setAutoFixAllowed] = useState(rule.auto_fix_allowed);
  const [sourceReference, setSourceReference] = useState(rule.source_reference ?? "");
  const [active, setActive] = useState(rule.active);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateRule(session, ruleSetId, rule.id, {
        category, requirement, validationMethod, severity, autoFixAllowed,
        sourceReference: sourceReference || undefined, active,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Edit ${rule.rule_id}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Saving…" : "Save changes"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Category</span>
          <input required value={category} onChange={(e) => setCategory(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Requirement</span>
          <textarea required value={requirement} onChange={(e) => setRequirement(e.target.value)} rows={3} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Validation method</span>
          <select value={validationMethod} onChange={(e) => setValidationMethod(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {VALIDATION_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Severity</span>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded">
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={autoFixAllowed} onChange={(e) => setAutoFixAllowed(e.target.checked)} />
          <span className="text-sm text-ink">Auto-fix allowed</span>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span className="text-sm text-ink">Active</span>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Source reference</span>
          <input value={sourceReference} onChange={(e) => setSourceReference(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}

function BulkUploadModal({
  session, ruleSetId, onClose, onDone,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  ruleSetId: number;
  onClose: () => void;
  onDone: (count: number) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setErrors(null);
    try {
      const result = await bulkUploadRules(session, ruleSetId, file);
      onDone(result.added);
    } catch (e) {
      if (e instanceof ApiError) {
        try {
          const parsed = JSON.parse(e.message);
          if (parsed && Array.isArray(parsed.errors)) {
            setErrors(parsed.errors);
          } else {
            setError(e.message);
          }
        } catch {
          setError(e.message);
        }
      } else {
        setError("Upload failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Upload Excel"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleUpload} disabled={busy || !file}>{busy ? "Uploading…" : "Upload"}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Uses the same column layout as the sample template. Every row is checked before anything
          is added — if any row has a problem, nothing will be added until it&apos;s fixed.
        </p>
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="w-full text-sm"
        />
        {error && <p className="text-sm text-brick">{error}</p>}
        {errors && (
          <div className="text-sm text-brick bg-brick/5 border border-brick/30 rounded p-3 max-h-48 overflow-auto">
            <p className="font-medium mb-1.5">Fix these and re-upload:</p>
            <ul className="list-disc list-inside space-y-0.5">
              {errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
}

function CloneModal({
  session, ruleSetId, onClose, onCloned,
}: {
  session: NonNullable<ReturnType<typeof useRequireSession>>;
  ruleSetId: number;
  onClose: () => void;
  onCloned: (id: number) => void;
}) {
  const [version, setVersion] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cloned = await cloneRuleSet(session, ruleSetId, version, name || undefined);
      onCloned(cloned.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not clone this rule set.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Clone as new version"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>{busy ? "Cloning…" : "Clone"}</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-muted">Creates a new draft with the same rules, which you can then edit.</p>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">New version</span>
          <input required value={version} onChange={(e) => setVersion(e.target.value)} placeholder="e.g. 0.5-draft" className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-ink mb-1.5">Name (optional — keeps the original name if blank)</span>
          <input value={name} onChange={(e) => setName(e.target.value)} className="focus-ring w-full border border-line bg-paper px-3 py-2 text-sm rounded" />
        </label>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </Modal>
  );
}
