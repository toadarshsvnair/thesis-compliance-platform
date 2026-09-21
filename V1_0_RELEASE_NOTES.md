# v1.0 Release Notes

## Architecture

The platform now separates synchronous API traffic from document processing using Redis and a dedicated worker process. The worker executes validation and LibreOffice rendering outside the API request path.

## Storage

Document versions can be copied to S3-compatible object storage while retaining a local processing copy. The database records an `object_uri` alongside the immutable SHA-256 hash.

## Operations

Prometheus metrics are exposed at `/api/metrics`. PostgreSQL schema changes are versioned through Alembic migrations. Deployment, backup and recovery runbooks are included.

## Security boundary

The worker is configured as a separate container with a read-only root filesystem, dropped Linux capabilities and a no-new-privileges setting. Further network egress restrictions and runtime sandboxing should be enforced by the deployment platform.

## Known residual work

- Configure a real managed OIDC provider and production secrets.
- Configure object-storage lifecycle/versioning and backup replication.
- Perform actual restore, tenant-isolation, fuzzing and DAST exercises in the target environment.
- Add a transactional outbox/reconciliation mechanism if Redis queue delivery requires stronger exactly-once operational guarantees.
- Replace development/local compose with the organization's Kubernetes or managed-container deployment standards if required.
