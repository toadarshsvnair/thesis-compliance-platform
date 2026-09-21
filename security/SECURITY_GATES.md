# v0.9 Production Security Gates

A release is not production-ready until these gates pass:

1. SAST: Bandit or equivalent; no unresolved high-confidence security findings.
2. SCA: pip-audit/SBOM review; no unresolved critical/high dependency vulnerabilities unless formally risk-accepted.
3. Secrets: Gitleaks or equivalent; no secrets committed to source.
4. Container: Trivy image/filesystem scan; no unresolved critical/high findings.
5. DAST: OWASP ZAP against a deployed test environment.
6. Authentication: production OIDC/OAuth2 enabled; development header authentication disabled.
7. Authorization: object-level and tenant-isolation matrix tests pass for every protected endpoint.
8. Upload security: DOCX package validation, size limits and malware scan pass before processing.
9. Processing isolation: document parsing/rendering executes in a dedicated worker/container with restricted filesystem/network permissions.
10. AI security: prompt-injection corpus, data-leakage tests, schema validation and tool-denial tests pass.
11. Audit integrity: hash-chain verification passes and audit storage is append-only to application roles.
12. Recovery: encrypted backups and restore test are completed for PostgreSQL and object storage metadata.
13. Migration: Alembic migrations are reviewed and applied in staging before production.
