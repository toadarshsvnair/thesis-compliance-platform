// Mirrors the FastAPI backend's actual response shapes exactly (see
// app/schemas.py, app/api/submissions.py, app/api/review.py, app/api/fixes.py,
// app/api/universities.py). Kept in one file so a backend contract change is
// one obvious place to update on this side.

export type Role = "student" | "research_officer" | "university_admin" | "super_admin";

export interface Session {
  token: string;
  userId: string;
  email: string;
  displayName: string;
  roles: Role[];
  universityIds: number[];
}

export interface University {
  id: number;
  name: string;
  code: string;
}

export interface Faculty {
  id: number;
  name: string;
  code: string;
}

export interface DocumentType {
  id: number;
  name: string;
  code: string;
}

export interface PublishedRuleSet {
  id: number;
  name: string;
  version: string;
  faculty_id: number | null;
  document_type_id: number | null;
}

export interface Submission {
  id: number;
  status: string;
  student_name: string;
  registration_number: string;
  current_version_id: number | null;
  findings_count: number;
  created_at: string;
}

export interface Finding {
  id: number;
  rule_id: string;
  category: string;
  severity: "Critical" | "Major" | "Review" | "Minor" | string;
  location: string;
  expected: string;
  actual: string;
  message: string;
  confidence: number | null;
  source_reference: string | null;
  auto_fix_allowed: boolean;
  status: "open" | "reviewed" | "rejected" | "waived" | "fix_approved" | "fixed" | "revalidation_failed" | string;
}

export interface DocumentVersion {
  id: number;
  version_number: number;
  filename: string;
  sha256: string;
  size_bytes?: number;
  parent_version_id: number | null;
  change_summary: string | null;
  created_by: string | null;
  created_at: string;
  is_current?: boolean;
}

export interface ComplianceDecisionSummary {
  decision: string;
  comment: string;
  actor_id: string;
  created_at: string;
}

export interface ReviewSummary {
  submission: {
    id: number;
    student_name: string;
    registration_number: string;
    programme: string | null;
    supervisor: string | null;
    status: string;
    current_version_id: number | null;
  };
  current_version: (DocumentVersion & { filename: string }) | null;
  finding_counts: Record<string, number>;
  total_findings: number;
  fixable_open_findings: number;
  latest_compliance_decision: ComplianceDecisionSummary | null;
}

export interface AuditEvent {
  id: number;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  document_version_id: number | null;
  result: string | null;
  metadata: Record<string, unknown>;
  previous_hash: string | null;
  event_hash: string | null;
  created_at: string;
}

export interface FixPreviewItem {
  finding_id: number;
  rule_id: string;
  location: string;
  operation: string;
  risk_note: string;
}

export interface FixPreviewOut {
  submission_id: number;
  source_version_id: number;
  items: FixPreviewItem[];
  blocked_finding_ids: number[];
}

export interface FixApplyOut {
  submission_id: number;
  source_version_id: number;
  target_version_id: number;
  target_version_number: number;
  applied_finding_ids: number[];
  revalidation_finding_count: number;
  revalidation_status: string;
}

export interface VersionCompare {
  source_version_id: number;
  target_version_id: number;
  source_version_number: number;
  target_version_number: number;
  text_changed: boolean;
  diff_lines: string[];
  source_sha256: string;
  target_sha256: string;
  change_summary: string | null;
}

export interface DemoBootstrap {
  university_id: number;
  university_name: string;
  rule_set_id: number | null;
  rule_set_name: string | null;
}
