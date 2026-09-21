"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRequireSession } from "@/lib/use-session";
import { clearSession, hasRole, ROLE_LABELS } from "@/lib/session";
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
import { Button, AppShell, Panel, SectionHeading, StatusBadge } from "@/components/ui";
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
    <AppShell
      active="/dashboard"
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
      <h1 className="font-serif text-2xl text-ink mb-8">Submissions</h1>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8">
        <section>
          <SectionHeading>All submissions</SectionHeading>
          {loadError && <p className="text-sm text-brick mb-4">{loadError}</p>}
          {submissions === null && !loadError && <p className="text-sm text-muted">Loading…</p>}
          {submissions && submissions.length === 0 && (
            <p className="text-sm text-muted">No submissions yet — create one from the panel on the right.</p>
          )}
          {submissions && submissions.length > 0 && (
            <Panel>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs font-medium text-muted">
                    <th className="px-4 py-3 font-medium">ID</th>
                    <th className="px-4 py-3 font-medium">Student</th>
                    <th className="px-4 py-3 font-medium">Registration #</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Findings</th>
                    <th className="px-4 py-3 font-medium">Submitted</th>
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
                      <td className="px-4 py-3 text-muted whitespace-nowrap">
                        {new Date(s.created_at).toLocaleString(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </td>
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
    </AppShell>
  );
}

function UploadPanel({ session, onCreated }: { session: NonNullable<ReturnType<typeof useRequireSession>>; onCreated: () => void }) {
  const isStudent = hasRole(session, "student") && !hasRole(session, "research_officer", "university_admin", "super_admin");

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
  const [programme, setProgramme] = useState("");
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
    listDocumentTypes(session, universityId).then(setDocumentTypes);
    if (!isStudent) listFaculties(session, universityId).then(setFaculties);
    listPublishedRuleSets(session, universityId).then((rows) => {
      setRuleSets(rows);
      setRuleSetId(rows.length > 0 ? rows[0].id : "");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    if (!universityId || !ruleSetId || !file || !documentTypeId) {
      setError("University, document type, rule set, and file are all required.");
      return;
    }
    if (!isStudent && (!studentName || !registrationNumber)) {
      setError("Student name and registration number are required.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createSubmission(session, {
        universityId,
        facultyId: !isStudent && facultyId ? facultyId : undefined,
        documentTypeId,
        ruleSetId,
        studentName: isStudent ? undefined : studentName,
        registrationNumber: isStudent ? undefined : registrationNumber,
        programme: !isStudent && programme ? programme : undefined,
        file,
      });
      setResult(`Submission #${created.id} created (${created.status}). Validation is running in the background.`);
      setStudentName("");
      setRegistrationNumber("");
      setProgramme("");
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
            {!isStudent && (
              <>
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
                <Field label="Programme (optional)">
                  <input
                    value={programme}
                    onChange={(e) => setProgramme(e.target.value)}
                    placeholder="e.g. PhD Computer Science"
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
              </>
            )}
            {isStudent && (
              <p className="text-xs text-muted -mt-2">
                Your name, registration number, programme, and faculty are taken from your account.
              </p>
            )}
            <Field label="Document type">
              <select
                required
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
                value={documentTypeId}
                onChange={(e) => setDocumentTypeId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="" disabled>
                  Select a document type
                </option>
                {documentTypes.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
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
            <Field label="Thesis file (.docx or .pdf)">
              <input
                required
                type="file"
                accept=".docx,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
              {file && file.name.toLowerCase().endsWith(".pdf") && (
                <p className="text-xs text-ochre mt-1.5">
                  Automated formatting checks require a DOCX and can&apos;t run on a PDF — this submission will be flagged for manual review instead.
                </p>
              )}
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
