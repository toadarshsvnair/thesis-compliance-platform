# v1.0 Production Deployment Runbook

1. Provision PostgreSQL, Redis, object storage and malware scanning service.
2. Store all credentials in the deployment secret manager; never commit `.env` files.
3. Configure OIDC issuer, audience and JWKS URL.
4. Create the object-storage bucket with private-by-default access and server-side encryption.
5. Run `alembic upgrade head` before starting application traffic.
6. Start the API and isolated processing worker as separate workloads.
7. Verify `/api/health` and `/api/metrics`.
8. Upload a harmless DOCX test file and confirm malware scanning, queueing, processing and audit events.
9. Execute tenant-isolation, authorization, upload-fuzzing and DAST gates before production traffic.
10. Configure PostgreSQL backups and perform a restore test before declaring the environment production-ready.

The worker should have no application secrets and should use restricted network egress. LibreOffice processing must occur only inside the worker boundary.
