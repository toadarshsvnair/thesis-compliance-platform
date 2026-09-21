# v0.9 Threat Model Addendum

## New trust boundaries
- Browser / API gateway -> API
- API -> PostgreSQL
- API -> object storage
- Upload quarantine -> malware scanner
- Upload quarantine -> isolated document worker
- API -> OIDC identity provider
- API -> AI provider
- CI/CD -> container registry

## Key controls
- OIDC/OAuth2 JWT validation with issuer, audience, signature and expiry checks.
- Production rejects development identity headers.
- Trusted hosts and explicit CORS origins.
- Request IDs and security headers.
- Upload size, ZIP structure, path traversal, entry count, compression ratio and uncompressed-size checks.
- Malware scanning with fail-closed option.
- Original document immutability and SHA-256 versioning.
- Tenant/object authorization on protected resources.
- AI treated as an untrusted processor; no tool access; structured output validation.
- SAST/SCA/secrets/container/DAST CI gates.
- Database migrations controlled by Alembic.

## Residual risk requiring deployment architecture
The API should not render untrusted DOCX files inside the same privileged process/container used for the public API. Production deployment must place document conversion/LibreOffice in a dedicated worker sandbox with a read-only base filesystem, ephemeral workspace, restricted egress and a non-root identity.
