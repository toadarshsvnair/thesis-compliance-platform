import type {
  AuditEvent,
  DemoBootstrap,
  DocumentType,
  DocumentVersion,
  Faculty,
  Finding,
  FixApplyOut,
  FixPreviewOut,
  PublishedRuleSet,
  ReviewSummary,
  Session,
  Submission,
  University,
  VersionCompare,
} from "./types";
import { sessionHeaders } from "./session";

// Same-origin "/api" by default (e.g. if this app is ever served behind the
// same reverse proxy as the backend); set NEXT_PUBLIC_API_BASE_URL to the
// backend's own origin (e.g. https://thesis-compliance-demo.onrender.com)
// when the frontend is deployed separately, which is the default setup for
// this project. See DEPLOY.md.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/api`
  : "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  session: Session,
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...sessionHeaders(session),
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  const text = await res.text();
  if (!res.ok) {
    let message = text;
    try {
      const parsed = JSON.parse(text);
      message = parsed.detail ? JSON.stringify(parsed.detail) : text;
    } catch {
      /* not JSON, use raw text */
    }
    throw new ApiError(res.status, message || `Request failed (${res.status})`);
  }
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

// ---- Authentication ----

export interface AuthResult {
  access_token: string;
  token_type: string;
  user: { id: number; email: string; display_name: string; roles: string[]; university_ids: number[] };
}

async function authRequest(path: string, body: unknown): Promise<AuthResult> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    let message = text;
    try {
      const parsed = JSON.parse(text);
      message = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message || `Request failed (${res.status})`);
  }
  return JSON.parse(text) as AuthResult;
}

export const login = (email: string, password: string) => authRequest("/auth/login", { email, password });

export const register = (input: {
  email: string;
  password: string;
  displayName: string;
  role: string;
  universityId: number;
}) =>
  authRequest("/auth/register", {
    email: input.email,
    password: input.password,
    display_name: input.displayName,
    role: input.role,
    university_id: input.universityId,
  });

// ---- Reference data ----

export const listUniversities = (session: Session) =>
  request<University[]>(session, "/universities");

export const listFaculties = (session: Session, universityId: number) =>
  request<Faculty[]>(session, `/universities/${universityId}/faculties`);

export const listDocumentTypes = (session: Session, universityId: number) =>
  request<DocumentType[]>(session, `/universities/${universityId}/document-types`);

export const listPublishedRuleSets = (
  session: Session,
  universityId: number,
  facultyId?: number,
  documentTypeId?: number
) => {
  const params = new URLSearchParams();
  if (facultyId) params.set("faculty_id", String(facultyId));
  if (documentTypeId) params.set("document_type_id", String(documentTypeId));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return request<PublishedRuleSet[]>(session, `/universities/${universityId}/rule-sets${qs}`);
};

export const getDevBootstrap = async (): Promise<DemoBootstrap | null> => {
  try {
    const res = await fetch(`${API_BASE}/dev/bootstrap`);
    if (!res.ok) return null;
    return (await res.json()) as DemoBootstrap;
  } catch {
    return null; // Not a demo deployment, or the API isn't reachable yet -- not an error a user needs to see here.
  }
};

// ---- Submissions ----

export const listSubmissions = (session: Session, params?: { status?: string; universityId?: number }) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.universityId) qs.set("university_id", String(params.universityId));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<Submission[]>(session, `/submissions${suffix}`);
};

export const getSubmission = (session: Session, id: number) =>
  request<Submission>(session, `/submissions/${id}`);

export const getReviewSummary = (session: Session, id: number) =>
  request<ReviewSummary>(session, `/submissions/${id}/review-summary`);

export const getFindings = (session: Session, id: number) =>
  request<Finding[]>(session, `/submissions/${id}/findings`);

export const getVersions = (session: Session, id: number) =>
  request<DocumentVersion[]>(session, `/submissions/${id}/versions`);

export const compareVersions = (session: Session, id: number, sourceVersionId: number, targetVersionId: number) =>
  request<VersionCompare>(session, `/submissions/${id}/versions/${sourceVersionId}/compare/${targetVersionId}`);

export const versionDownloadUrl = (id: number, versionId: number) =>
  `${API_BASE}/submissions/${id}/versions/${versionId}/download`;

export const getAuditTrail = (session: Session, id: number) =>
  request<AuditEvent[]>(session, `/submissions/${id}/audit`);

export const triggerValidation = (session: Session, id: number) =>
  request<{ submission_id: number; version_id: number; status: string; job_id: string }>(
    session,
    `/submissions/${id}/validate`,
    { method: "POST" }
  );

export interface CreateSubmissionInput {
  universityId: number;
  facultyId?: number;
  documentTypeId?: number;
  ruleSetId: number;
  studentName: string;
  registrationNumber: string;
  programme?: string;
  supervisor?: string;
  file: File;
}

export const createSubmission = (session: Session, input: CreateSubmissionInput) => {
  const fd = new FormData();
  fd.set("university_id", String(input.universityId));
  if (input.facultyId) fd.set("faculty_id", String(input.facultyId));
  if (input.documentTypeId) fd.set("document_type_id", String(input.documentTypeId));
  fd.set("rule_set_id", String(input.ruleSetId));
  fd.set("student_name", input.studentName);
  fd.set("registration_number", input.registrationNumber);
  if (input.programme) fd.set("programme", input.programme);
  if (input.supervisor) fd.set("supervisor", input.supervisor);
  fd.set("file", input.file);
  return request<Submission>(session, "/submissions", { method: "POST", body: fd });
};

// ---- Review actions ----

export const reviewFinding = (
  session: Session,
  submissionId: number,
  findingId: number,
  action: "reviewed" | "rejected" | "waived",
  comment: string
) =>
  request<{ finding_id: number; status: string }>(
    session,
    `/submissions/${submissionId}/findings/${findingId}/review`,
    { method: "POST", body: JSON.stringify({ action, comment }) }
  );

export const recordComplianceDecision = (
  session: Session,
  submissionId: number,
  decision: "compliant" | "returned",
  comment: string
) =>
  request<{ submission_id: number; version_id: number; decision: string; status: string }>(
    session,
    `/submissions/${submissionId}/review/decision`,
    { method: "POST", body: JSON.stringify({ decision, comment }) }
  );

// ---- Controlled auto-fix ----

export const getFixableFindings = (session: Session, submissionId: number) =>
  request<Array<{ id: number; rule_id: string; location: string; expected: string; actual: string; message: string; operation: string }>>(
    session,
    `/submissions/${submissionId}/fixable-findings`
  );

export const previewFixes = (session: Session, submissionId: number, findingIds: number[]) =>
  request<FixPreviewOut>(session, `/submissions/${submissionId}/fixes/preview`, {
    method: "POST",
    body: JSON.stringify({ finding_ids: findingIds, confirm: false }),
  });

export const applyFixes = (session: Session, submissionId: number, findingIds: number[]) =>
  request<FixApplyOut>(session, `/submissions/${submissionId}/fixes/apply`, {
    method: "POST",
    body: JSON.stringify({ finding_ids: findingIds, confirm: true }),
  });

// ---- Certificate ----

export const generateCertificate = (session: Session, submissionId: number) =>
  request<{ certificate_id: string; download_url: string; version_id: number }>(
    session,
    `/submissions/${submissionId}/certificate`,
    { method: "POST" }
  );

export const certificateDownloadUrl = (id: number) => `${API_BASE}/submissions/${id}/certificate/download`;
export const evaluationReportUrl = (id: number) => `${API_BASE}/submissions/${id}/evaluation-report`;

// Plain <a href> links can't attach the X-User-* auth headers a browser
// navigation needs, so downloads go through fetch() (which can) and then
// simulate a click on the resulting blob instead.
export async function downloadFile(session: Session, url: string, filename: string): Promise<void> {
  const res = await fetch(url, { headers: sessionHeaders(session) });
  if (!res.ok) {
    throw new ApiError(res.status, `Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
