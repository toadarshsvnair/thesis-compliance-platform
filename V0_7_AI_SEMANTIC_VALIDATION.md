# v0.7 — AI Semantic Validation Layer

## Design principles

1. Deterministic rules remain authoritative for measurable formatting and structure.
2. AI is used only for semantic/ambiguous checks that deterministic parsing cannot establish reliably.
3. Document-derived text is treated as untrusted data and never as instructions.
4. AI cannot auto-fix findings.
5. Every AI finding is marked `requires_human_review=true`.
6. The platform records provider, model, prompt version, input hash and response hash for auditability.
7. The default provider is `mock`, so local development does not send thesis content externally.
8. A production provider must be explicitly configured with `AI_PROVIDER=openai_compatible`, `AI_API_KEY`, and `AI_MODEL`.
9. Only minimized structured evidence is sent; raw DOCX bytes are never sent to the model.
10. Academic quality, originality, authorship and research-claim correctness are outside the AI compliance scope.

## API

`POST /api/submissions/{id}/ai/analyze`

Runs AI semantic analysis against the current immutable document version.

## Prompt-injection controls

- Explicit system instruction that document text is untrusted data.
- No tool access is granted to the model.
- Structured evidence instead of raw document upload.
- Rule allow-list: model output is discarded unless its rule ID is active for the submission.
- Confidence threshold of 0.70 for creating a finding.
- Strict output schema validation.
- All AI findings require human review.

## Production gates

Before enabling an external provider for production:

- establish data-processing/privacy terms and retention settings;
- test prompt-injection and indirect-injection corpora;
- test data exfiltration and cross-tenant isolation;
- test malformed/hostile DOCX evidence;
- add provider timeout, retry, circuit-breaker and quota controls;
- log only hashes/metadata rather than full prompts or thesis text where possible;
- add SCA/SAST/DAST and secret scanning to CI/CD.
