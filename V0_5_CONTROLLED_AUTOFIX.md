# v0.5 — Controlled Auto-Fix + Immutable Versioning

## Purpose
Allow an authorized Research Officer / University Admin / Super Admin to approve a narrowly allow-listed formatting fix. The original document is never overwritten.

## Workflow
1. Validate a document version and create findings.
2. `GET /api/submissions/{id}/fixable-findings` lists only open findings that are both marked auto-fixable and present in the v0.5 safety allow-list.
3. `POST /api/submissions/{id}/fixes/preview` shows the selected operations before change.
4. `POST /api/submissions/{id}/fixes/apply` requires explicit `confirm=true`.
5. The API locks the submission row, verifies the selected findings belong to the current version, creates a new version, and applies only the selected formatting operations.
6. A safety guard compares visible document text and basic structure before/after. If content changes, the target version is rejected and the source remains intact.
7. The new version is automatically rendered/revalidated.
8. Audit events record approval, version creation, and revalidation. A `FixApproval` record links finding -> source version -> target version -> actor.

## Safe v0.5 allow-list
- PAGE-001 to PAGE-005
- FONT-001
- FONT-002
- TAB-003
- FIG-003
- REF-002

The allow-list is intentionally smaller than the complete rule catalogue. Content changes, cross-reference repair, TOC repair, title-page rewriting, reference-content changes, and table/figure content changes are not permitted through this service.

## Important production notes
- v0.5 development authentication still uses the v0.4 development headers; replace with OIDC/OAuth2 JWT validation before production.
- Database schema changes currently rely on `create_all()` for a fresh development database. Production requires a migration tool such as Alembic.
- Malware scanning remains a production gate from v0.4.
- Python-docx is used for controlled formatting. The visible-text safety check reduces risk but is not a substitute for a full OOXML package-preservation test corpus.
- The revalidation step is synchronous in this MVP. Production should move it to a durable background queue with idempotency and job state.
