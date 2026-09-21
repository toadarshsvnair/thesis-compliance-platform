# Thesis Compliance Platform v1.0 — Multi-University Production Architecture

v1.0 packages the functional platform with a production-oriented deployment boundary:

- University-scoped tenancy and rule-set versioning
- Secure DOCX upload and malware scanning
- Immutable document versions and audit trails
- Deterministic validation + AI semantic validation with human review
- Controlled formatting-only auto-fix
- PostgreSQL as the system of record
- Redis-backed asynchronous processing queue
- Dedicated document-processing worker
- S3-compatible object storage support
- Prometheus-compatible metrics
- OIDC/OAuth2 production authentication baseline
- Alembic migration workflow
- Production Docker Compose reference architecture
- Backup/recovery and deployment runbooks

## Local development

Use the existing development compose file for the local API workflow. Production-like deployment is documented in `docker-compose.v1.yml`.

## Production startup order

1. Configure secrets and OIDC settings.
2. Provision PostgreSQL, Redis, object storage and ClamAV.
3. Run `alembic upgrade head`.
4. Start API and worker separately.
5. Verify health/metrics.
6. Execute security gates and a restore test before accepting university traffic.

The production compose file is a reference architecture, not a claim that a production environment has been provisioned or independently security-certified.
