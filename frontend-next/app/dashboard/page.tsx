"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRequireSession } from "@/lib/use-session";
import { clearSession, ROLE_LABELS } from "@/lib/session";
import {
  ApiError,
  createSubmission,
  listDocumentTypes,
  listFaculties,
  listPublishedRuleSets,
  listSubmissions,
  listUniversities,
} from "@/lib/api";
import type { DocumentType, Faculty, PublishedRuleSet, Submission, University } from "@/lib/types";
import { Button, Panel, SectionHeading, StatusBadge } from "@/components/ui";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const session = useRequireSession();
  const router = useRouter();

  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!session) return;
    listSubmissions(session)
      .then(setSubmissions)
      .catch((e) => setLoadError(e instanceof ApiError ? e.message : "Could not load submissions."));
  }, [session]);

  useEffect(refresh, [refresh]);

  if (!session) return null;

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <header className="flex items-start justify-between mb-8 pb-6 border-b border-line">
        <div>
          <h1 className="font-serif text-2xl text-ink">Thesis Compliance Platform</h1>
          <p className="text-sm text-muted mt-1">
            Signed in as {session.email} · {session.roles.map((r) => ROLE_LABELS[r]).join(", ")}
          </p>
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            clearSession();
            router.replace("/login");
          }}
        >
          Sign out
        </Button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8">
        <section>
          <SectionHeading>Submissions</SectionHeading>
          {loadError && <p className="text-sm text-brick mb-4">{loadError}</p>}
          {submissions === null && !loadError && <p className="text-sm text-muted">Loading…</p>}
          {submissions && submissions.length === 0 && (
            <p className="text-sm text-muted">No submissions yet — create one from the panel on the right.</p>
          )}
          {submissions && submissions.length > 0 && (
            <Panel>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium">ID</th>
                    <th className="px-4 py-3 font-medium">Student</th>
                    <th className="px-4 py-3 font-medium">Registration #</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Findings</th>
                  </tr>
                </thead>
                <tbody>
                  {submissions.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-line last:border-0 hover:bg-navy/[0.03] cursor-pointer"
                      onClick={() => router.push(`/submissions/${s.id}`)}
                    >
                      <td className="px-4 py-3">
                        <Link href={`/submissions/${s.id}`} className="text-navy hover:underline">
                          #{s.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3">{s.student_name}</td>
                      <td className="px-4 py-3 text-muted">{s.registration_number}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="px-4 py-3 text-muted">{s.findings_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}
        </section>

        <UploadPanel session={session} onCreated={refresh} />
      </div>
    </main>
  );
}

function UploadPanel({ session, onCreated }: { session: NonNullable<ReturnType<typeof useRequireSession>>; onCreated: () => void }) {
  const [universities, setUniversities] = useState<University[]>([]);
  const [universityId, setUniversityId] = useState<number | null>(null);
  const [faculties, setFaculties] = useState<Faculty[]>([]);
  const [facultyId, setFacultyId] = useState<number | "">("");
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [documentTypeId, setDocumentTypeId] = useState<number | "">("");
  const [ruleSets, setRuleSets] = useState<PublishedRuleSet[]>([]);
  const [ruleSetId, setRuleSetId] = useState<number | "">("");

  const [studentName, setStudentName] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    listUniversities(session)
      .then((rows) => {
        setUniversities(rows);
        if (rows.length > 0) setUniversityId(rows[0].id);
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.message : "Could not load universities."));
  }, [session]);

  useEffect(() => {
    if (!universityId) return;
    listFaculties(session, universityId).then(setFaculties);
    listDocumentTypes(session, universityId).then(setDocumentTypes);
    listPublishedRuleSets(session, universityId).then((rows) => {
      setRuleSets(rows);
      setRuleSetId(rows.length > 0 ? rows[0].id : "");
    });
  }, [session, universityId]);

  useEffect(() => {
    if (!universityId) return;
    listPublishedRuleSets(
      session,
      universityId,
      facultyId || undefined,
      documentTypeId || undefined
    ).then((rows) => {
      setRuleSets(rows);
      setRuleSetId(rows.length > 0 ? rows[0].id : "");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facultyId, documentTypeId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!universityId || !ruleSetId || !file) {
      setError("University, rule set and file are all required.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createSubmission(session, {
        universityId,
        facultyId: facultyId || undefined,
        documentTypeId: documentTypeId || undefined,
        ruleSetId,
        studentName,
        registrationNumber,
        file,
      });
      setResult(`Submission #${created.id} created (${created.status}). Validation is running in the background.`);
      setStudentName("");
      setRegistrationNumber("");
      setFile(null);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <aside>
      <SectionHeading>New submission</SectionHeading>
      <Panel className="p-5">
                {loadError ? (
          <p className="text-sm text-brick">{loadError}</p>
        ) : universities.length === 0 ? (
          <p className="text-sm text-muted">
            No universities are configured for your account yet. A University Admin needs to set one up.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {universities.length > 1 && (
              <Field label="University">
                <select
                  className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
                  value={universityId ?? ""}
                  onChange={(e) => setUniversityId(Number(e.target.value))}
                >
                  {universities.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Student name">
              <input
                required
                value={studentName}
                onChange={(e) => setStudentName(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Registration number">
              <input
                required
                value={registrationNumber}
                onChange={(e) => setRegistrationNumber(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            {faculties.length > 0 && (
              <Field label="Faculty (optional)">
                <select
                  className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
                  value={facultyId}
                  onChange={(e) => setFacultyId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">—</option>
                  {faculties.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {documentTypes.length > 0 && (
              <Field label="Document type (optional)">
                <select
                  className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
                  value={documentTypeId}
                  onChange={(e) => setDocumentTypeId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">—</option>
                  {documentTypes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Rule set">
              {ruleSets.length === 0 ? (
                <p className="text-sm text-brick">No published rule set is available for this selection.</p>
              ) : (
                <select
                  className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
                  value={ruleSetId}
                  onChange={(e) => setRuleSetId(Number(e.target.value))}
                >
                  {ruleSets.map((rs) => (
                    <option key={rs.id} value={rs.id}>
                      {rs.name} ({rs.version})
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Thesis file (.docx)">
              <input
                required
                type="file"
                accept=".docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
            </Field>
            {error && <p className="text-sm text-brick">{error}</p>}
            {result && <p className="text-sm text-forest">{result}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Uploading…" : "Upload & validate"}
            </Button>
          </form>
        )}
      </Panel>
    </aside>
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
