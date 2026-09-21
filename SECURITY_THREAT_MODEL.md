
# Thesis Compliance Platform — v0.4 Threat Model

## Assets

1. Student thesis documents
2. Student identity and registration information
3. Supervisor/research-officer information
4. University rule sets and templates
5. Validation findings
6. Approved corrected document versions
7. Audit events
8. AI prompts, extracted text and AI responses
9. Credentials, signing keys and database secrets

## Trust boundaries

### TB-1: Browser → API
Threats:
- stolen session/token
- malformed requests
- oversized uploads
- CSRF where cookie-based auth is used

Controls:
- OIDC/OAuth2
- short-lived tokens
- secure cookie strategy where applicable
- request validation
- rate limiting
- security headers

### TB-2: API → File Storage
Threats:
- path traversal
- unauthorized object access
- storage misconfiguration
- accidental overwrite

Controls:
- generated storage paths
- filename sanitization
- tenant/object authorization
- immutable document versions
- SHA-256 integrity

### TB-3: Upload → Document Worker
Threats:
- malware
- malicious OOXML
- ZIP bombs
- parser vulnerabilities
- resource exhaustion
- embedded external content

Controls:
- malware scan before processing
- OOXML package validation
- isolated worker/container
- CPU/memory/time limits
- no outbound network by default
- read-only source document
- disposable workspace

### TB-4: Document → AI Layer
Threats:
- prompt injection inside document
- indirect instructions
- sensitive-data leakage
- excessive AI agency
- fabricated citations/changes

Controls:
- treat document text as untrusted data
- separate system instructions from document content
- structured extraction
- least-privilege AI tools
- no autonomous submission approval
- no autonomous academic-content modification
- human approval for semantic findings

### TB-5: API → Database
Threats:
- SQL injection
- broken object-level authorization
- cross-university data access

Controls:
- SQLAlchemy parameterization
- authorization on every object access
- university_id scoping
- database least privilege
- audit events

## STRIDE summary

| Threat | Example | Primary control |
|---|---|---|
| Spoofing | forged identity | OIDC/OAuth2 |
| Tampering | altered thesis/version | SHA-256 + immutable versions |
| Repudiation | disputed approval | audit trail |
| Information disclosure | cross-university finding access | tenant/object authorization |
| Denial of service | ZIP bomb | package limits + worker quotas |
| Elevation of privilege | Research Officer accesses admin functions | RBAC |

## Security testing gates

Before production:
- SAST
- dependency/SCA scan
- secrets scan
- container scan
- DAST
- upload fuzzing
- malicious DOCX/OOXML test corpus
- authorization matrix tests
- tenant-isolation tests
- prompt-injection test corpus
- audit integrity tests
