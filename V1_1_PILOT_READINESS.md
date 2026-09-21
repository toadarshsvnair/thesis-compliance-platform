# v1.1 — Pilot Readiness & Compliance Certificate

v1.1 adds the final institutional workflow needed for an initial university pilot:

- Human compliance decision remains authoritative.
- A compliance certificate can only be generated for the current document version after an explicit `compliant` decision.
- Certificate records student/submission metadata, document version, SHA-256, rule-set version, decision actor/date and officer comment.
- Certificate explicitly disclaims originality/authorship/scholarly-merit assessment.
- Critical/major unresolved findings block certificate generation.
- Certificate generation is tenant-authorized and restricted to review roles.

## Pilot acceptance sequence

1. Configure university/faculty/document type.
2. Publish the approved rule set.
3. Configure OIDC and production secrets.
4. Upload a thesis and confirm malware scan.
5. Wait for asynchronous validation completion.
6. Review findings and perform approved safe fixes.
7. Revalidate the resulting version.
8. Record the human compliance decision.
9. Generate and download the certificate.
10. Verify audit trail, rule-set version and document SHA-256.
11. Execute backup/restore and tenant-isolation tests before pilot sign-off.

The certificate is a workflow record, not an academic-quality or originality guarantee.
