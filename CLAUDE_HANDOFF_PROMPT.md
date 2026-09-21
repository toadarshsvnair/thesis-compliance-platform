# Claude Handoff Prompt — Thesis Compliance Platform

You are taking over an existing software project called **Thesis Compliance Platform**. Do not restart the project from scratch. Treat the repository you received as the current baseline and evolve it carefully.

## Mission

Turn the current v1.2 reference implementation into a deployable, secure, production-quality university thesis/document compliance platform.

The product checks uploaded DOCX theses against university-specific formatting and structural rules, uses AI only for ambiguous semantic checks, provides controlled formatting-only auto-fix, requires human review/approval, maintains immutable document versions and audit trails, and generates a human-gated compliance certificate.

## Non-negotiable principles

- Deterministic validation is authoritative for measurable rules.
- AI is assistive, not authoritative.
- AI must never approve a thesis.
- AI must never change academic content.
- AI must never invent or modify citations/references.
- AI must not have database, filesystem, shell, email, or administrative tool access.
- Uploaded documents are untrusted input.
- Never overwrite the original document.
- Every modification creates a new immutable version and requires revalidation.
- Human decision is mandatory for final compliance.
- Enforce university/tenant isolation at every object access.
- Published rule sets are immutable.
- Every important action must be auditable.
- Fail closed on malware scanning/security-critical ingestion controls.

## Current baseline

The repository contains the v1.2 implementation with:

- FastAPI backend
- PostgreSQL-ready SQLAlchemy models
- Alembic migrations framework
- Redis-backed processing architecture
- dedicated worker
- object storage abstraction
- ClamAV integration boundary
- deterministic DOCX/PDF validation engine
- AI semantic validation boundary
- controlled auto-fix
- immutable versioning
- human review
- human compliance decision
- certificate generation
- university/faculty/document/rule-set/rule management
- audit integrity
- production security controls
- pilot operations gates
- tests
- lightweight review frontend

Read the repository files before changing architecture. In particular inspect:

- `README.md`
- `FINAL_TECHNICAL_DOCUMENTATION.md`
- `SECURITY_THREAT_MODEL.md`
- `V1_2_PILOT_OPERATIONS.md`
- `ops/DEPLOYMENT_RUNBOOK.md`
- `ops/BACKUP_RECOVERY.md`
- `security/SECURITY_GATES.md`
- `app/models.py`
- `app/main.py`
- `app/config.py`
- `app/security/*`
- `app/services/*`
- `app/api/*`
- `engine/thesis_compliance_engine_v0_2.py`
- `worker/processing_worker.py`
- `tests/*`

## Product scope

Initial pilot:

- Alliance University
- PhD thesis
- DOCX
- approved Annexure 18 template
- approved Annexure 19 thesis preparation/formatting guideline
- additional explicitly documented institutional rules

Required checks include:

- preliminary page sequence
- List of Abbreviations
- A4 page size
- margins
- Times New Roman and paragraph formatting
- title page
- chapters/sections
- table formatting
- figure formatting
- numbering
- body cross-references
- broken references
- TOC integrity
- citation/reference consistency
- reference formatting/hanging indentation
- appendices
- rendered-page evidence

## Required user roles

- Super Admin
- University Admin
- Research Officer
- Student

## Required workflows

### University Admin

Create/configure university, faculty, document type, upload guideline source, create/clone rule set, edit draft rules, publish immutable rule set, archive old versions.

### Research Officer

Create/receive submission, inspect validation report, review findings, waive/reject findings with rationale, preview/apply approved safe formatting fixes, revalidate, record final human compliance decision, generate certificate when eligible.

### Student

Submit a document and view the status/findings that their authorization permits. Student must never access another student's submission.

## Architecture target

Preferred pilot cloud: Google Cloud, Mumbai (`asia-south1`). Avoid Kubernetes for the first pilot unless a concrete requirement emerges.

Target:

- web/API service
- PostgreSQL
- object storage
- queue/Redis
- isolated processing worker
- ClamAV
- secrets manager
- monitoring/logging
- real OIDC/OAuth2

Keep document processing isolated from the API and application secrets.

## Frontend target

Replace the current lightweight HTML dashboard with a production-grade Next.js/React frontend.

Required screens:

1. Login
2. Dashboard
3. University administration
4. Faculty management
5. Document type management
6. Rule-set management
7. Guideline source management
8. Submission creation/upload
9. Processing/job status
10. Compliance findings
11. Finding detail/evidence
12. Review/waiver workflow
13. Auto-fix preview
14. Version history
15. Document comparison
16. Audit trail
17. Human compliance decision
18. Certificate download
19. Student submission/status
20. Security/admin operations where appropriate

Use accessible UI patterns, server-side authorization checks, and do not rely on hidden frontend controls as security.

## AI layer

AI should handle only cases that are genuinely ambiguous, such as:

- semantic interpretation of heading/section sequence
- citation/reference plausibility
- ambiguous reference entries
- abbreviation consistency

Return strict structured output. Validate every AI response against a schema. Store model/provider/prompt-version metadata and hashes required for auditability.

Do not send the complete document to an external model unless there is a documented need and appropriate privacy/security approval. Prefer minimized evidence.

## Auto-fix rules

Safe auto-fix may cover:

- A4 page size
- margins
- font
- first-line indentation
- table caption formatting
- figure caption formatting
- reference hanging indent/spacing

Do not auto-fix:

- academic prose
- title wording
- citation content
- reference content
- table data
- figure data
- scholarly claims
- cross-reference meaning
- authorship/content

Every auto-fix requires explicit human approval, creates a new version, preserves the original, and triggers revalidation.

## Security requirements

Implement and test:

- OIDC/JWT signature, issuer, audience, expiry validation
- secure cookies/token handling as appropriate
- CSRF protection where cookie-based auth is used
- tenant isolation
- object-level authorization
- upload size/type limits
- DOCX magic/package validation
- ZIP bomb/path traversal defenses
- malware scanning
- worker isolation
- restricted egress
- no-new-privileges
- non-root execution
- secret management
- rate limiting
- security headers
- request IDs
- audit integrity
- backup/restore
- retention/deletion controls
- dependency/SCA scanning
- SAST
- secret scanning
- container scanning
- DAST
- malicious DOCX corpus
- prompt-injection corpus

## Quality gates

Before calling a release complete:

1. Run the complete test suite.
2. Add tests for every new endpoint and authorization path.
3. Test tenant isolation.
4. Test malicious uploads.
5. Test prompt injection.
6. Test auto-fix immutability.
7. Test certificate eligibility.
8. Run static/security scans.
9. Run an E2E workflow from upload to certificate.
10. Update documentation.
11. Record known limitations honestly.

Do not claim penetration testing, security certification, legal compliance, or production readiness unless actually performed and evidenced.

## Important source/rule governance

Do not silently invent university requirements. The rule catalogue must distinguish:

- source-derived requirements from Annexure 18/19
- additional institutional rules explicitly provided by the university
- implementation assumptions

Faculty-specific citation/reference styles must remain configurable.

## Immediate work order

Do these in order:

### Phase 1 — Understand

- inspect the complete repository
- run the current tests
- map existing APIs/models/services
- identify gaps and technical debt
- do not rewrite working components without reason

### Phase 2 — Frontend

Build the production Next.js/React frontend against the existing API contracts. Preserve backend authorization as the source of truth.

### Phase 3 — Identity

Implement real OIDC/OAuth2 and remove development header identity from staging/production paths.

### Phase 4 — Infrastructure

Create infrastructure-as-code for the recommended cloud architecture, with separate dev/staging/prod environments.

### Phase 5 — Worker hardening

Ensure all document parsing/rendering happens in the isolated worker, with resource limits, restricted egress, no app secrets, and strong input validation.

### Phase 6 — E2E

Implement an automated E2E test covering:

upload → scan → queue → validation → findings → review → approved safe fix → new version → revalidation → compliant decision → certificate.

### Phase 7 — Security

Execute the complete security gates and remediate findings.

### Phase 8 — Pilot

Configure Alliance University and import the approved rule set. Use sample theses first. Measure accuracy and turnaround time before real student use.

## Output expected from you

Produce:

1. Updated source code
2. Production frontend
3. Infrastructure-as-code
4. Database migrations
5. Complete API documentation/OpenAPI
6. Security architecture and threat model
7. Deployment runbook
8. Backup/restore runbook
9. User/admin documentation
10. Rule-management documentation
11. Test plan and test evidence
12. E2E test
13. CI/CD pipeline
14. Release notes
15. Known limitations and residual risks

When making changes, explain what changed, why it changed, how it was tested, and what remains.

Do not merely generate another prototype. Continue the existing implementation toward a deployable product.
