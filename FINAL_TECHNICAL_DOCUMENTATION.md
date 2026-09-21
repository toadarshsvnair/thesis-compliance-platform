# Thesis Compliance Platform — Final Technical Handoff

## 1. Purpose

A secure, multi-university platform for checking thesis/document-formatting compliance against university-approved rules. The platform combines deterministic document validation with optional AI-assisted semantic analysis, controlled formatting-only auto-fix, human review, immutable document versions, audit trails, and a human-gated compliance certificate.

The initial pilot target is Alliance University PhD thesis compliance using the approved Annexure 18 template and Annexure 19 thesis preparation/formatting guideline, plus explicitly identified additional institutional rules.

## 2. Design Principles

1. Deterministic rules are authoritative for measurable formatting and structural requirements.
2. AI is assistive only for ambiguous semantic checks.
3. AI cannot approve a submission, modify academic content, or execute tools.
4. Uploaded documents are untrusted input.
5. Original documents are immutable.
6. Every approved modification creates a new document version.
7. Revalidation is mandatory after modification.
8. Human approval is required for compliance decisions and non-deterministic findings.
9. University/tenant boundaries are enforced at the API and data-access layers.
10. Rule sets are versioned and published versions are immutable.
11. Audit records are chained using hashes to provide tamper-evidence.
12. The system must fail closed for security-critical controls such as malware scanning.

## 3. Current Functional Scope

### Roles

- Super Admin
- University Admin
- Research Officer
- Student

### University configuration

University → Faculty → Document Type → Rule Set → Rules.

Rule sets support Draft → Published → Archived lifecycle. Published rule sets are immutable; changes require a new version/clone.

### Submission metadata

At minimum:

- Student name
- Registration number
- Programme
- Faculty
- Supervisor
- Document type
- University
- Selected rule set

### Validation categories

- Preliminary-page sequence
- Page size and margins
- Fonts and paragraph formatting
- Title page
- Introduction/front matter
- Chapter and section structure
- Tables
- Figures
- Table/figure numbering
- Body cross-references
- Broken cross-references
- Table of contents
- Citations and references
- Appendices
- Rendered-page/pagination evidence
- AI-assisted semantic checks

### Controlled auto-fix

Allowlisted formatting fixes can include:

- A4 page size
- margins
- Times New Roman font
- first-line indentation
- table caption formatting
- figure caption formatting
- reference hanging indentation and spacing

Academic/content changes are blocked. The system must not rewrite thesis text, invent citations, alter citation content, repair scholarly meaning, or silently change tables/figures.

### Human review

A Research Officer can review findings and record actions such as reviewed, rejected, or waived. Waivers/review actions require a comment.

The final compliance decision is human-gated:

- Compliant
- Returned for Correction

A rationale is mandatory.

### Compliance certificate

A certificate can be generated only after an authorized human marks the exact document version compliant and no unresolved Critical/Major findings remain. The certificate is bound to:

- document version
- SHA-256
- rule-set version
- student/registration/programme/faculty
- reviewing officer
- decision date

The certificate explicitly does not certify originality, authorship, academic quality, or scholarly merit.

## 4. Processing Architecture

```text
Browser / University Users
          |
          v
   API / Web Application
          |
   +------+----------------+
   |                       |
   v                       v
PostgreSQL             Object Storage
   |
   +---- Audit / Rules / Findings / Versions
   |
   v
Redis / Queue
   |
   v
Dedicated Processing Worker
   |
   +--> Malware Scan (ClamAV)
   +--> OOXML/ZIP validation
   +--> LibreOffice rendering
   +--> Deterministic engine
   +--> Rendered PDF checks
   +--> AI semantic analysis (optional)
   |
   v
Findings / Validation Result
   |
   v
Human Review
   |
   +--> Approved safe fix -> New version -> Revalidation
   |
   v
Human Compliance Decision
   |
   v
Certificate
```

## 5. Security Architecture

### Trust boundaries

1. Browser → API
2. API → database
3. API → object storage
4. Upload → processing worker
5. Document content → AI service
6. Worker → external services

### Required controls

- OIDC/OAuth2/JWT in staging/production
- No trust in development `X-User-*` headers outside local development
- University-scoped authorization
- Object-level submission authorization
- Secure filename handling
- DOCX magic/package validation
- ZIP path-traversal checks
- ZIP entry-count and decompressed-size limits
- Compression-ratio limits
- Upload size limits
- Malware scanning with fail-closed behavior
- Read-only worker filesystem where possible
- Non-root worker container
- Dropped Linux capabilities
- no-new-privileges
- Restricted worker egress
- No application secrets in the worker
- CORS allow-list
- Trusted Host controls
- HSTS in production
- Request IDs
- Rate limiting
- Immutable versioning
- Hash-chained audit events
- Secret management outside source control

### AI security

Document text is untrusted. Prompt injection and indirect instruction attacks must be treated as data, not instructions.

The AI provider receives minimized structured evidence where practical rather than an unrestricted raw document. The AI provider has no application tools, database access, filesystem access, or authority to approve or modify submissions.

AI responses must pass strict schema validation and rule-ID allowlisting. Provider/model/prompt version and relevant input/response hashes should be auditable.

## 6. Data Model

Core entities include:

- University
- Faculty
- DocumentType
- RuleSet
- Rule
- User
- UserRole
- Submission
- DocumentVersion
- Finding
- AuditEvent

Important relationships:

```text
University
  ├── Faculties
  ├── Users
  ├── Rule Sets
  └── Submissions

RuleSet
  └── Rules

Submission
  ├── Document Versions
  ├── Findings
  └── Audit Events

DocumentVersion
  └── parent_version_id -> previous version
```

## 7. API Surface

Health/operations:

- `GET /api/health`
- `GET /api/metrics`

Submission:

- `POST /api/submissions`
- `GET /api/submissions/{id}`
- `GET /api/submissions/{id}/findings`
- `POST /api/submissions/{id}/validate`
- `GET /api/submissions/{id}/versions`
- `GET /api/submissions/{id}/versions/{version_id}/download`
- `GET /api/submissions/{id}/audit`

Review:

- `GET /api/submissions/{id}/review-summary`
- `POST /api/submissions/{id}/findings/{finding_id}/review`
- `POST /api/submissions/{id}/review/decision`

Controlled fixes:

- `GET /api/submissions/{id}/fixable-findings`
- `POST /api/submissions/{id}/fixes/preview`
- `POST /api/submissions/{id}/fixes/apply`
- `GET /api/submissions/{id}/versions/{parent}/compare/{child}`

AI:

- `POST /api/submissions/{submission_id}/ai/analyze`

Certificates:

- `POST /api/submissions/{id}/certificate`
- `GET /api/submissions/{id}/certificate/download`

Rules:

Rule-management endpoints are implemented in `app/api/rules.py`; inspect that file for the exact current request/response contracts before extending the API.

## 8. Rule Governance

Each rule should contain:

- rule ID
- category
- requirement
- validation method
- expected value/condition
- severity
- auto-fix allowed
- source reference
- active state
- rule-set version

Rules sourced from Annexure 18/19 must retain the exact source reference used during configuration. Additional institutional rules must be clearly labelled as additional institutional requirements.

For Alliance University, the rule catalogue should cover the documented requirements for:

- A4 paper
- margins
- Times New Roman
- preliminary-page sequence
- title page
- chapter/section formatting
- table and figure captions
- table/figure numbering
- body references
- list of abbreviations
- references and hanging indentation
- TOC integrity
- appendices
- other applicable faculty-specific requirements

Faculty-specific citation/reference styles must remain configurable rather than hard-coded globally.

## 9. DevSecOps

CI should run:

1. Unit/integration tests
2. Bandit SAST
3. Dependency/SCA scan
4. Secrets scan
5. Container vulnerability scan
6. DAST/ZAP against a test deployment
7. Authorization matrix tests
8. Tenant-isolation tests
9. Malicious DOCX/OOXML corpus tests
10. Prompt-injection corpus tests
11. Audit-integrity tests

Do not treat a green application test suite as proof of production security certification.

## 10. Deployment Target

Recommended pilot architecture: Google Cloud, primary workload in Mumbai (`asia-south1`).

Reference services:

- Cloud Run for API/web workloads
- Dedicated worker service/container
- Cloud SQL for PostgreSQL
- Cloud Storage for document objects
- Redis-compatible queue service or managed Redis
- Secret Manager
- Artifact Registry
- VPC/network controls
- Cloud Logging/Monitoring
- Cloud KMS where required

Do not deploy the worker with broad public access. Keep document processing behind the queue/service boundary.

## 11. Pilot Workflow

```text
Configure University
  -> Publish Rule Set
  -> Create User Accounts
  -> Upload Thesis
  -> Malware Scan
  -> Immutable Version
  -> Queue Processing
  -> Deterministic Validation
  -> Rendered Validation
  -> Optional AI Analysis
  -> Human Review
  -> Approved Safe Fixes
  -> New Version
  -> Revalidation
  -> Human Decision
  -> Certificate
```

## 12. Pilot Success Criteria

The pilot should measure:

- validation turnaround time
- Research Officer review time
- false positives
- false negatives/missed findings
- safe-fix success rate
- revalidation success rate
- tenant-isolation test results
- security test results
- certificate traceability
- user feedback

Do not claim a reduction in verification time until measured against a defined manual baseline.

## 13. Production Gaps / Explicit Non-Claims

This repository is a production-oriented reference implementation and pilot handoff. It is not evidence that a production cloud environment has been provisioned, independently penetration-tested, formally certified, or approved by Alliance University.

Before production use:

- configure real OIDC
- configure production secrets
- provision production databases/storage/queue
- configure ClamAV and verify fail-closed behavior
- deploy isolated worker infrastructure
- configure backup and restore
- configure monitoring/alerting
- complete security gates
- complete privacy/retention review
- complete incident-response readiness
- complete E2E testing
- complete Research Office acceptance

Known code-level cleanup items from the current test run include Pydantic class-based Config deprecation and FastAPI `on_event` deprecation warnings. They do not currently fail the test suite but should be cleaned up before a long-lived production release.

## 14. Current Verification

The v1.2 application test suite was executed during handoff and completed with 19 passing tests and 3 deprecation warnings. The warnings are documented above.

## 15. Repository Guide

- `app/` — FastAPI application, models, APIs, services, security
- `engine/` — deterministic thesis validation engine
- `worker/` — asynchronous processing worker
- `frontend/` — current lightweight human-review browser dashboard
- `security/` — security gates and threat-model material
- `ops/` — deployment and backup/recovery runbooks
- `tests/` — application/security/feature tests
- `alembic/` — database migration framework
- `V0_*` / `V1_*` — feature/release documentation

## 16. Engineering Direction for the Next Release

The next release should focus on production implementation rather than another conceptual prototype:

1. Build a production-grade Next.js/React frontend.
2. Replace development identity headers with real OIDC integration.
3. Complete cloud infrastructure as code.
4. Move all long-running document work to the isolated worker path.
5. Add managed object storage with lifecycle/retention controls.
6. Add robust job-status UX and retries/dead-letter handling.
7. Add comprehensive rule-management UX.
8. Add student submission UX.
9. Add Research Office dashboards and analytics.
10. Add visual document-diff/review where useful.
11. Harden AI provider integration.
12. Complete security and operational acceptance testing.
