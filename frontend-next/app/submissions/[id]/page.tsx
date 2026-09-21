"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useRequireSession } from "@/lib/use-session";
import { hasRole } from "@/lib/session";
import {
  ApiError,
  applyFixes,
  certificateDownloadUrl,
  compareVersions,
  downloadFile,
  evaluationReportUrl,
  generateCertificate,
  getAuditTrail,
  getFindings,
  getReviewSummary,
  getVersions,
  previewFixes,
  recordComplianceDecision,
  reviewFinding,
  versionDownloadUrl,
} from "@/lib/api";
import type { AuditEvent, DocumentVersion, Finding, FixPreviewOut, ReviewSummary, VersionCompare } from "@/lib/types";
import { Button, Masthead, Panel, SectionHeading, SeverityBadge, StatusBadge } from "@/components/ui";

const REVIEW_ROLES = ["research_officer", "university_admin", "super_admin"] as const;

export default function SubmissionDetailPage() {
  const session = useRequireSession();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[] | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<FixPreviewOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [compare, setCompare] = useState<VersionCompare | null>(null);

  const canReview = hasRole(session ?? null, ...REVIEW_ROLES);

  const refreshAll = useCallback(() => {
    if (!session || !id) return;
    setError(null);
    Promise.all([getReviewSummary(session, id), getFindings(session, id), getVersions(session, id), getAuditTrail(session, id)])
      .then(([s, f, v, a]) => {
        setSummary(s);
        setFindings(f);
        setVersions(v);
        setAudit(a);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load this submission."));
  }, [session, id]);

  useEffect(refreshAll, [refreshAll]);

  if (!session) return null;
  if (error) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <Button variant="ghost" onClick={() => router.push("/dashboard")}>
          ← Back to dashboard
        </Button>
        <p className="text-brick mt-4">{error}</p>
      </main>
    );
  }
  if (!summary || !findings || !versions || !audit) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <p className="text-muted text-sm">Loading…</p>
      </main>
    );
  }

  async function toggleSelected(findingId: number) {
    const next = new Set(selected);
    next.has(findingId) ? next.delete(findingId) : next.add(findingId);
    setSelected(next);
    setPreview(null);
  }

  async function handlePreview() {
    if (!session || selected.size === 0) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await previewFixes(session, id, Array.from(selected)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    if (!session || selected.size === 0) return;
    if (!confirm("Create a new immutable document version and revalidate it?")) return;
    setBusy(true);
    setError(null);
    try {
      const result = await applyFixes(session, id, Array.from(selected));
      setSelected(new Set());
      setPreview(null);
      alert(`Created version v${result.target_version_number} and revalidated (${result.revalidation_finding_count} finding(s) remain).`);
      refreshAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Applying fixes failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReviewAction(findingId: number, action: "reviewed" | "rejected" | "waived") {
    if (!session) return;
    const comment = prompt(`Comment for marking this finding "${action}":`);
    if (!comment) return;
    setBusy(true);
    try {
      await reviewFinding(session, id, findingId, action, comment);
      refreshAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Review action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(decision: "compliant" | "returned") {
    if (!session) return;
    const comment = prompt(`Rationale for recording "${decision === "compliant" ? "Compliant" : "Returned for Correction"}":`);
    if (!comment) return;
    setBusy(true);
    try {
      await recordComplianceDecision(session, id, decision, comment);
      refreshAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Recording the decision failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateCertificate() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await generateCertificate(session, id);
      await downloadFile(session, certificateDownloadUrl(id), `certificate-submission-${id}.pdf`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Certificate generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadEvaluationReport() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await downloadFile(session, evaluationReportUrl(id), `evaluation-report-submission-${id}.pdf`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Report generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCompare(sourceId: number, targetId: number) {
    if (!session) return;
    try {
      setCompare(await compareVersions(session, id, sourceId, targetId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Comparison failed.");
    }
  }

  const s = summary.submission;

  return (
    <>
      <Masthead subtitle="Submission review" />
      <main className="max-w-5xl mx-auto px-6 py-10">
      <Button variant="ghost" onClick={() => router.push("/dashboard")} className="mb-6 !px-0">
        ← Back to dashboard
      </Button>

      <header className="mb-8 pb-6 border-b border-line">
        <div className="flex items-baseline justify-between flex-wrap gap-2">
          <h1 className="font-serif text-2xl text-ink">
            {s.student_name} <span className="text-muted font-sans text-lg">— {s.registration_number}</span>
          </h1>
          <div className="flex items-center gap-3">
            <StatusBadge status={s.status} />
            <Button variant="ghost" disabled={busy} onClick={handleDownloadEvaluationReport}>
              Download evaluation report (PDF)
            </Button>
          </div>
        </div>
        {(s.programme || s.supervisor) && (
          <p className="text-sm text-muted mt-1">
            {s.programme}
            {s.supervisor ? ` · Supervisor: ${s.supervisor}` : ""}
          </p>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
          <Metric label="Current version" value={summary.current_version ? `v${summary.current_version.version_number}` : "—"} />
          <Metric label="Total findings" value={String(summary.total_findings)} />
          <Metric label="Fixable now" value={String(summary.fixable_open_findings)} />
          <Metric
            label="Decision"
            value={summary.latest_compliance_decision ? summary.latest_compliance_decision.decision : "Pending"}
          />
        </div>
      </header>

      {error && <p className="text-sm text-brick mb-6">{error}</p>}

      <section className="mb-10">
        <SectionHeading>Findings</SectionHeading>
        {findings.length === 0 ? (
          <p className="text-sm text-muted">No findings on the current version.</p>
        ) : (
          <Panel>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  {canReview && <th className="px-4 py-3 w-8"></th>}
                  <th className="px-4 py-3 font-medium">Rule</th>
                  <th className="px-4 py-3 font-medium">Severity</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Message</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  {canReview && <th className="px-4 py-3 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {findings.map((f) => (
                  <tr key={f.id} className="border-b border-line last:border-0 align-top">
                    {canReview && (
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          disabled={!f.auto_fix_allowed || f.status !== "open"}
                          checked={selected.has(f.id)}
                          onChange={() => toggleSelected(f.id)}
                        />
                      </td>
                    )}
                    <td className="px-4 py-3 font-mono text-xs">{f.rule_id}</td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={f.severity} />
                    </td>
                    <td className="px-4 py-3 text-muted">{f.location}</td>
                    <td className="px-4 py-3">
                      <p>{f.message}</p>
                      <p className="text-xs text-muted mt-1">
                        Expected: {f.expected} · Actual: {f.actual}
                      </p>
                      {f.source_reference && (
                        <p className="text-xs text-muted italic mt-0.5">Guideline: {f.source_reference}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={f.status} />
                    </td>
                    {canReview && (
                      <td className="px-4 py-3">
                        {f.status === "open" && (
                          <div className="flex gap-2">
                            <Button variant="ghost" onClick={() => handleReviewAction(f.id, "reviewed")}>
                              Mark reviewed
                            </Button>
                            <Button variant="ghost" onClick={() => handleReviewAction(f.id, "waived")}>
                              Waive
                            </Button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )}

        {canReview && findings.some((f) => f.auto_fix_allowed && f.status === "open") && (
          <div className="mt-4 flex items-center gap-3">
            <Button variant="secondary" disabled={selected.size === 0 || busy} onClick={handlePreview}>
              Preview selected fixes
            </Button>
            <Button disabled={selected.size === 0 || busy} onClick={handleApply}>
              Apply selected fixes
            </Button>
            <span className="text-sm text-muted">{selected.size} selected</span>
          </div>
        )}
        {preview && (
          <Panel className="mt-4 p-4">
            <p className="text-sm font-medium mb-2">Preview</p>
            <ul className="text-sm space-y-1">
              {preview.items.map((item) => (
                <li key={item.finding_id}>
                  <span className="font-mono text-xs">{item.rule_id}</span> — {item.operation}
                </li>
              ))}
            </ul>
            {preview.blocked_finding_ids.length > 0 && (
              <p className="text-xs text-brick mt-2">Blocked (not eligible): {preview.blocked_finding_ids.join(", ")}</p>
            )}
          </Panel>
        )}
      </section>

      <section className="mb-10">
        <SectionHeading>Version history</SectionHeading>
        <div className="space-y-2">
          {versions.map((v) => (
            <Panel key={v.id} className="p-4 flex items-center justify-between flex-wrap gap-2">
              <div>
                <p className="text-sm">
                  <span className="font-medium">v{v.version_number}</span>
                  {v.is_current && <span className="text-forest text-xs ml-2">(current)</span>}
                  {" — "}
                  {v.filename}
                </p>
                <p className="text-xs text-muted mt-0.5">
                  {v.change_summary ?? "Original submission"} · SHA-256 {v.sha256.slice(0, 16)}…
                </p>
              </div>
              <div className="flex gap-3">
                <Button variant="ghost" onClick={() => session && downloadFile(session, versionDownloadUrl(id, v.id), v.filename)}>
                  Download
                </Button>
                {v.parent_version_id && (
                  <Button variant="ghost" onClick={() => handleCompare(v.parent_version_id as number, v.id)}>
                    Compare with parent
                  </Button>
                )}
              </div>
            </Panel>
          ))}
        </div>
        {compare && (
          <Panel className="mt-4 p-4">
            <p className="text-sm font-medium mb-2">
              v{compare.source_version_number} → v{compare.target_version_number}:{" "}
              {compare.text_changed ? (
                <span className="text-brick">visible text changed (unexpected for a formatting-only fix)</span>
              ) : (
                <span className="text-forest">visible text unchanged</span>
              )}
            </p>
            {compare.diff_lines.length > 0 && (
              <pre className="text-xs bg-paper border border-line p-3 overflow-auto max-h-64">
                {compare.diff_lines.join("\n")}
              </pre>
            )}
          </Panel>
        )}
      </section>

      <section className="mb-10">
        <SectionHeading>Audit trail</SectionHeading>
        <Panel className="p-4 max-h-72 overflow-auto">
          <ol className="text-xs font-mono space-y-2">
            {audit.map((e) => (
              <li key={e.id} className="text-muted">
                <span className="text-ink">{e.action}</span> · {e.actor_id} ·{" "}
                {new Date(e.created_at).toLocaleString()} {e.result ? `· ${e.result}` : ""}
              </li>
            ))}
          </ol>
        </Panel>
      </section>

      {canReview && (
        <section>
          <SectionHeading>Human compliance decision</SectionHeading>
          <p className="text-sm text-muted mb-4">
            Recording a decision requires a rationale and applies to the current document version (v
            {summary.current_version?.version_number ?? "—"}).
          </p>
          <div className="flex gap-3 flex-wrap">
            <Button disabled={busy} onClick={() => handleDecision("compliant")}>
              Record Compliant
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => handleDecision("returned")}>
              Return for Correction
            </Button>
            {summary.latest_compliance_decision?.decision === "compliant" && (
              <Button variant="secondary" disabled={busy} onClick={handleGenerateCertificate}>
                Generate & download certificate
              </Button>
            )}
          </div>
        </section>
      )}
      </main>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="text-lg font-serif text-ink capitalize">{value}</p>
    </div>
  );
}
