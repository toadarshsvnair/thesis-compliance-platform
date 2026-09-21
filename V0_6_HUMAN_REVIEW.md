# v0.6 — Human Review & Approval Dashboard

## Purpose

v0.6 adds a browser-based human review workflow around the deterministic validator and controlled auto-fix service. The platform does not infer the final academic/compliance decision; the authorized Research Officer, University Admin, or Super Admin records it explicitly.

## Added capabilities

- Review summary for the current immutable document version.
- Findings list with severity, status, location, expected vs actual and auto-fix eligibility.
- Preview and apply selected controlled formatting fixes.
- Human finding actions: reviewed, rejected, waived, each with a required comment.
- Document version history and SHA-256 values.
- Parent/child version comparison with visible-text diff guard.
- Secure document-version download subject to submission authorization.
- Audit trail view including chained audit hashes.
- Explicit human compliance decision: `compliant` or `returned`, with rationale.

## Review principle

The system records the authorized human decision. It does not rank submissions, infer a decision from the findings, or silently waive findings.

## Development dashboard

Start the API and open:

`http://localhost:8000/review`

The dashboard currently uses the v0.4/v0.5 development identity headers. These headers are not production authentication and must be replaced by OIDC/OAuth2 JWT validation.

## Production hardening still required

- Real OIDC/OAuth2 identity and session management.
- CSRF strategy for cookie-based authentication, if used.
- Malware scanning.
- Isolated document worker and resource limits.
- Object storage instead of local filesystem.
- PostgreSQL migrations with Alembic.
- Centralized logging/monitoring/SIEM integration.
- SAST, SCA, secrets, container and DAST gates.
- UI security review and accessibility testing.
