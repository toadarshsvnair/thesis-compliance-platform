# v0.8 — University Rule Management

v0.8 adds governed, university-scoped rule administration.

## Lifecycle
`draft -> published -> archived`

Published rule sets are immutable. Administrators clone a published rule set to a new version, edit the draft, then publish it. Existing submissions retain their original `rule_set_id`, preserving reproducibility.

## Scope
A rule set belongs to one university and may optionally be scoped to one faculty and one document type.

## Guideline sources
Admins can attach PDF, DOCX, or TXT guideline sources to a draft. The service records label, sanitized filename, SHA-256, size, and immutable storage path in source metadata. Rules retain a human-readable `source_reference` such as `Annexure 19, p. 6`.

## Publication guardrails
A draft cannot be published when it is empty or an active rule lacks a source reference. AI-assisted/human rules cannot be configured for auto-fix.

## Authorization
Only `university_admin` and `super_admin` can administer rules. University admins remain tenant-scoped. Development header identity remains local-only and must be replaced with validated OIDC/OAuth2 before production.

## API
- `POST /api/admin/rules/rule-sets`
- `GET /api/admin/rules/rule-sets?university_id=...`
- `POST /api/admin/rules/rule-sets/{id}/clone`
- `POST /api/admin/rules/rule-sets/{id}/rules`
- `PATCH /api/admin/rules/rule-sets/{id}/rules/{rule_id}`
- `POST /api/admin/rules/rule-sets/{id}/sources`
- `POST /api/admin/rules/rule-sets/{id}/publish`
- `POST /api/admin/rules/rule-sets/{id}/archive`
