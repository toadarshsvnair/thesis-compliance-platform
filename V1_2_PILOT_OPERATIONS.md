# v1.2 — Pilot Operations & Go-Live Controls

This release adds operational controls for a controlled university pilot. It does not represent independent security certification or production deployment.

## Pilot gates

1. Identity provider configured and tested.
2. PostgreSQL backup and restore test completed.
3. Object-storage lifecycle and encryption configured.
4. ClamAV service reachable and fail-closed behavior tested.
5. Worker has restricted egress and no application secrets.
6. Tenant-isolation authorization tests pass.
7. SAST/SCA/secrets/container/DAST gates pass in CI.
8. Rule-set source documents and versions approved by the University.
9. Privacy notice, retention period, and deletion process approved.
10. Incident escalation contacts confirmed.
11. Pilot users trained on human-review and certificate workflows.
12. One non-production end-to-end thesis test completed before live student data.

## Data governance

The pilot should define retention for original documents, derived PDFs, findings, audit records, and certificates. Deletion must preserve required audit evidence while removing documents when the approved retention period expires.

## Incident response

Security events should be classified, assigned an owner, contained, investigated, and closed with an auditable record. Suspected malicious documents must be quarantined and not passed to the document-processing worker.

## Go-live principle

The platform may process real student documents only after the University signs off the environment-specific gates above. Passing automated tests alone is not a production authorization.
