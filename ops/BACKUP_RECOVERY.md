# Backup and Recovery Requirements

- PostgreSQL: daily full backup plus point-in-time recovery where supported by the managed service.
- Object storage: versioning enabled; retention policy and encrypted backup replica configured by the deployment team.
- Redis: treat as recoverable queue state, not the system of record.
- Audit records: retain according to university policy; protect against deletion by application users.
- Recovery test: perform a documented restore test at least quarterly and record RTO/RPO results.
