# v1.0 Multi-University Production Architecture

## Tenant boundary
University is the primary tenant boundary. Faculty, document type, rule set, submission, findings and guideline sources are university-scoped.

## Processing boundary
API accepts metadata and secure uploads. A queue separates API traffic from document processing. A dedicated worker performs LibreOffice rendering and validation. The worker is isolated from application secrets.

## Storage
Production object storage is S3-compatible and private by default. Database records store metadata and immutable version references; document bytes are not exposed directly through the API without authorization.

## Operations
PostgreSQL is the system of record. Redis is a queue/cache component. Prometheus-compatible metrics expose request and processing counters. Backups and recovery are operational requirements rather than application-level claims.

## Human governance
Compliance decisions remain human-authorized. AI findings require human review. Controlled auto-fix creates immutable versions and triggers revalidation.
