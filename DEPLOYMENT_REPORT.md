# Thesis Compliance Platform — Deployment Report

**From:** ChatGPT-authored v1.2 handoff baseline
**To:** A live, working demo deployment
**Live demo:** https://thesis-compliance-demo.onrender.com (or your Render-assigned URL if it differs)
**Status date:** current as of this conversation

---

## 1. Executive Summary

The platform arrived as a well-documented but never-actually-run reference implementation: a FastAPI backend, a deterministic DOCX compliance engine, a lightweight review dashboard, and an extensive set of design documents describing a production architecture that had not yet been built. The handoff package itself was explicit that this was a baseline, not a deployed system.

Two rounds of work got it from that state to a live, clickable deployment:

1. **Code audit (Phase 1)** — read every file in the repository, cross-referenced the shipped rule catalogue spreadsheet against the actual validation engine, and verified findings by executing code rather than only reading it. This surfaced bugs that made the core validation engine non-functional as packaged, and a large gap between the approved rule catalogue and what the engine actually checks.
2. **Live deployment** — turned the fixed baseline into a real, internet-reachable demo on Render's free tier, which in turn surfaced four *additional* bugs that static code review had not caught, because they only manifest when a real request hits a real running server.

The system now runs end-to-end in production conditions (as a demo, not a hardened deployment): upload → malware/package validation → LibreOffice rendering → deterministic compliance engine → findings displayed in a browser → controlled auto-fix → human review → compliance decision → certificate.

---

## 2. Starting Point: What Phase 1 Found

Full detail is in `PHASE1_FINDINGS.md` (delivered earlier); summarized here for completeness.

| # | Finding | Verified by |
|---|---|---|
| 1 | `app/services/validator.py` computed the compliance engine's file path one directory level too high (`parents[3]` instead of `parents[2]`) | Imported the module directly, confirmed the computed path didn't exist, confirmed `run_validation()` raised `CalledProcessError` |
| 2 | The `Dockerfile` never copied `engine/` into the image at all — independent of bug #1, the engine script simply wasn't in the container | Read the Dockerfile's `COPY` lines directly |
| 3 | A double-backslash inside a raw-string regex (`r"^CHAPTER\\s+..."`) silently disabled chapter-sequence and TOC-completeness checks — matched a literal backslash character instead of whitespace, so it never matched real text | Built a synthetic document with chapters deliberately out of order; confirmed 0 findings before the fix, correct findings after; re-confirmed against the real sample thesis (found a genuine ordering issue: `[1, 1, 2, 3, 4, 5, 2, 3, 4, 5, 6]`) |
| 4 | The approved rule catalogue (`Thesis_Compliance_MVP_Requirements_and_Rule_Catalogue_v0.3.xlsx`) lists 62 rules; the engine can only ever emit 27 of them — 35 rules (56%), including **all** appendix checks and most pagination-format checks, have no implementation at all. Three more rule IDs mean something different in code than in the catalogue (`REF-001`, `CHAP-001`, `PRE-001`) | Extracted both rule-ID lists programmatically and diffed them |
| 5 | `authorize_submission()` unconditionally rejects any principal with the `student` role — the Student workflow described in the product requirements has no working code path | Read the authorization code directly |
| 6 | `app/seed_rules.py` seeded a rule set with `status="active"`, which isn't a valid state anywhere else in the app (the real lifecycle is `draft → in_review → published → retired`), so the seed data could never actually be used | Read the rule-set lifecycle logic in `app/api/rules.py` |

Findings #1, #2, #3, and #6 were fixed directly in code (each independently verified before and after). #4 and #5 were left as documented, scoped gaps rather than patched blind, since closing them requires either substantial new rule-engine logic or a schema/product decision, not a bug fix.

---

## 3. From Fixed Code to a Live Demo

Getting the fixed baseline actually running live required a deliberate scope decision, since the architecture described in the handoff documents (real OIDC, GCP infrastructure, isolated worker, ClamAV, Redis-backed queue) is a multi-week production build, not a next step. The choice made — confirmed with you before building anything — was: **get a real, working, $0/month demo live first**, explicitly not production-grade, and treat everything in it as disposable.

Concrete changes made for this:

| Change | Reason |
|---|---|
| Validation now falls back to an in-process FastAPI background task when `REDIS_URL` isn't set (new file: `app/services/inline_processing.py`) | Render's free tier doesn't support a separate Background Worker service at all — avoids that cost/complexity entirely for a low-traffic demo. The original Redis+worker path is untouched and still used automatically if `REDIS_URL` is ever configured. |
| Auto-seeded demo data on startup, gated behind a `DEMO_SEED` flag (`app/seed_rules.py`, `app/main.py`) | The app had no admin UI for creating a University/Rule Set — without this, there was no way to create a submission at all through the browser. |
| Added an actual upload form to `frontend/index.html` | The dashboard could only *review* an existing submission by ID; there was no way to create one except a raw `curl`/API call. |
| `/` now redirects to `/review` | Previously 404'd — nothing served the dashboard at the site root. |
| `render.yaml` (new) | Render's infrastructure-as-code format — declares the web service and free Postgres database in one file, including correctly wiring the database connection string and generating a random `SECRET_KEY`, so the whole stack deploys from one "Deploy Blueprint" click rather than manual dashboard configuration. |

---

## 4. Bugs Found *During* Deployment (that code review alone didn't catch)

This is the most important section for anyone assessing how thorough "code review" can actually be. All four of these only became visible once a real browser made real requests to a real running server — none would have been caught by reading the code, and none were caught by the existing pytest suite either (which doesn't exercise the Docker image, the dashboard in a browser, or a real Postgres connection).

| Issue | Symptom | Root cause | Fix |
|---|---|---|---|
| **Missing `frontend/` in Docker image** | Whole-page "Internal Server Error" on every visit to the site | The `Dockerfile` copied `app/`, `worker/`, `engine/` but never `frontend/` — the exact same class of bug as the missing `engine/` copy from Phase 1, which I should have caught at the same time and didn't | Added `COPY frontend ./frontend` |
| **Postgres connection string driver mismatch** | Would have caused every database connection to fail outright | Render's managed Postgres hands out a bare `postgresql://` URL; SQLAlchemy defaults that scheme to the `psycopg2` driver, which isn't installed (this project uses `psycopg` v3) | `app/db.py` now auto-upgrades any bare `postgresql://` URL to `postgresql+psycopg://` before creating the engine; URLs that already specify a driver are left untouched |
| **`ALLOWED_HOSTS` blocking Render's own health checks** | Continuous `400 Bad Request` in the logs, deploy stuck in a fail/restart loop despite the app itself starting successfully | `TrustedHostMiddleware` was locked to only the public `onrender.com` hostname; Render's internal health-checker probes from a private cluster IP with a different `Host` header, which got rejected by our own security check | `ALLOWED_HOSTS` relaxed to `*` for this demo deployment |
| **Content-Security-Policy blocking the dashboard's own inline CSS/JS** | Page loaded with zero styling, every button silently did nothing when clicked, "Demo University" showed as an empty string | The app's global CSP header (`default-src 'self'`, no `'unsafe-inline'`) blocks inline `<style>`, inline `<script>`, and `onclick="..."` attributes in any standards-compliant browser. **This bug predates all of this work — it was in the original ChatGPT-authored v0.6 dashboard code and was never caught, because nothing in the test suite loads the page in an actual browser with these headers active.** | `SecurityHeadersMiddleware` now serves a relaxed CSP (`'unsafe-inline'` for script/style) only for the `/review` path; every JSON API response keeps the original strict policy |

The last one is worth sitting with: it's a genuine pre-existing defect in code that shipped in the original handoff, undetected through however many rounds of that code being written and "tested" previously, because the specific failure mode (a security header silently disabling a page's own functionality) only shows up when you actually load the page in a browser that enforces CSP — not when reading the code, and not in a headless API test.

---

## 5. Current State of the Live Demo

**What works, end to end, live on the internet right now:**
- Upload a `.docx` → filename/size/DOCX-package validation → malware-scan check (no-op in this config, see limitations) → immutable version created
- Validation runs automatically in the background (LibreOffice render → deterministic engine) — no manual trigger needed
- Findings display with rule ID, severity, location, expected vs. actual, confidence
- Controlled auto-fix: preview and apply allow-listed formatting fixes, which creates a new immutable version and automatically revalidates it
- Human review actions (reviewed / rejected / waived) with mandatory comments
- Version history, parent/child comparison, SHA-256 tracked per version
- Full audit trail with hash-chained events
- Human compliance decision (Compliant / Returned for Correction)
- Certificate generation and PDF download, gated on an actual compliant decision and no unresolved Critical/Major findings

**What this demo deliberately is not** (all explicit, agreed trade-offs for getting something real running at $0):
- Authentication is hardcoded development headers, not real OIDC — anyone with the URL has full Research Officer access
- No malware scanning is actually active
- No separate isolated worker — validation runs in the same process as the API
- Free Postgres expires 30 days after creation and is capped at 1 GB
- Uploaded files do not survive a redeploy or spin-down (ephemeral filesystem)
- 512 MB RAM ceiling — a large, image-heavy thesis may fail; the real sample thesis you provided (182 rendered pages, 53 images) is a reasonable stress test if you want to check this
- Rule coverage now at 49 of 62 catalogued rules (79%) — see Section 6 for what's still missing and why
- Student role still non-functional (Phase 1 finding #5, unchanged)

**Do not put real student names, real theses, or any real institutional data into this deployment.** It has none of the safeguards that would make that appropriate, by design.

---

## 6. Closing the Rule-Catalogue Gap

Phase 1 found the engine implemented only 27 of the 62 rules in the approved catalogue (44%). Since a well-hosted tool that misses 56% of what the university actually asked for isn't "ready" regardless of infrastructure, this was closed next, using the same evidence-based approach as Phase 1: every new check was verified against the real sample thesis before being considered done, not just read through.

**Result: 49 of 62 rules now implemented (79%).**

New or corrected checks, all confirmed against the real thesis:

| Rule(s) | What changed | Verified |
|---|---|---|
| `PRE-002`–`PRE-012` | Each missing preliminary section now reports its own correct rule ID (was previously reported as generic `PRE-001` for all eleven) | Confirmed the two genuinely-missing sections in the real thesis (Preface, List of Appendices) now report as `PRE-007` and `PRE-012` respectively, not both as `PRE-001` |
| `PRE-001` | Added: flags when no distinct title-page content precedes the first preliminary section | Correctly does *not* fire on the real thesis (which has ~11 lines of genuine title-page content) |
| `INTRO-001`/`INTRO-002` | Style of each preliminary-section heading, and its immediately following body text | Real thesis's Declaration/Acknowledgement/Abstract headings all correctly pass `INTRO-001`; one body-text style deviation correctly caught by `INTRO-002` |
| `TITLE-003` | Institution name/address line style, found by content pattern rather than position | Correctly identifies "ALLIANCE UNIVERSITY" specifically (not the earlier incidental mention "Thesis submitted to Alliance University") and flags its actual 14pt-bold styling against the prescribed 12pt-regular |
| `CHAP-001` (fixed) | Chapter-heading detection tightened to require the *entire* paragraph be just "CHAPTER N" | Removes a real false-positive: the real thesis has both actual `CHAPTER 1` headings and unrelated narrative sentences starting "Chapter 1 – This chapter provides...", which the old looser pattern counted as the same thing |
| `CHAP-002` | Style of the descriptive chapter title immediately following "CHAPTER N" (e.g. "INTRODUCTION") | Correctly passes on the real thesis's compliant chapter headings |
| `SEC-001`/`SEC-002`/`SEC-003` | Section/subsection/sub-subsection heading style, by numbering depth (`1.1`, `1.1.1`, `1.2.2.1`) | Correctly recognizes the real thesis's headings as compliant at all three levels (no false positives on already-correct formatting) |
| `TAB-002`/`FIG-002` | Caption position relative to its table/figure | `TAB-002`: zero false positives (real thesis's captions are consistently positioned correctly). `FIG-002`: caught one real instance of a caption with no image nearby |
| `APP-001`/`APP-002` | Appendix presence/consistency and body cross-references | Logic mirrors the already-proven `TAB-005`/`FIG-004` pattern; the real thesis has no appendices, so this couldn't be exercised against a positive case, only confirmed to correctly produce zero false positives on a document with none |

**Explicitly not implemented, each for a stated reason rather than a fragile guess:**

| Rule(s) | Why not |
|---|---|
| `TITLE-002` | The catalogue models "author/course" as one styled line; real theses (confirmed against the sample) split this across several distinct lines with no reliable positional marker for which one is "the" line. Forcing a heuristic risks confidently flagging the wrong line. Better suited to the AI-assisted layer or a catalogue revision. |
| `PRE-015`, `SEC-004` | Require comparing against the rendered PDF's table of contents, following the same pattern as the existing `TOC-002` check — not implemented this pass, but a natural next addition using the same infrastructure. |
| `PAGE-006`–`PAGE-009` | Page-numbering *format* (roman numerals, arabic numbers restarting at 1, fresh page per chapter) can only be verified against the rendered PDF, not DOCX XML. Couldn't be tested in this environment (no PyMuPDF available here), though the deployed app has it — worth verifying against the live demo. |
| `FONT-004` (widow/orphan) | Fundamentally a page-layout question; even with rendered-PDF access this only supports a low-fidelity heuristic. |
| `TAB-006` | "If reproduced from elsewhere, cite the source" isn't deterministically decidable — whether a table came from another source is a judgment call, not a formatting check. |
| `REF-003`/`REF-004` | Citation-to-reference resolution needs style-aware parsing (the catalogue itself specifies this varies by faculty: APA vs. Bluebook vs. Chicago) — a real feature, not a quick addition. |
| `SUB-001`/`SUB-002` | About validating a *multi-file submission package*; the platform currently only accepts one `.docx` per submission. This needs a data-model change, not a rule-engine fix. |

One architectural note worth flagging: the deterministic engine runs its full fixed rule set on every submission regardless of what's configured in the database's `RuleSet`/`Rule` tables — the University Admin rule-governance UI (draft → published → archived, source references, etc.) doesn't actually control which deterministic checks execute. That's pre-existing behavior, not something introduced here, but it means the "governed rule catalogue" the product design describes isn't yet connected to the engine that runs it. Worth knowing about for whoever works on this next.

## 7. Production Frontend (Phase 2) — First Batch

Built a real Next.js 14 (App Router, TypeScript, Tailwind) frontend as a separate deployment from the backend — the standard architecture for a Python API + JS frontend, communicating over HTTP with CORS. Scoped as the core submission/review workflow rather than all 20 screens from the handoff spec at once: `/login` (dev-mode placeholder), `/dashboard` (list + create submissions), and `/submissions/[id]` (findings, review actions, controlled auto-fix, version history/comparison, audit trail, compliance decision, certificate). Admin screens (university/rule-set/guideline management) are a natural second batch, mapping to backend endpoints that already exist but have no frontend yet.

**A real constraint on how this was verified, stated plainly:** this sandbox has no network access to install `next`, so this code has never been run through `next build` or `next dev`. What I could and did do: type-checked every file against the real `react`/`typescript` packages in strict mode (zero errors), and every API call is written against the exact backend response shapes by reading the actual route handlers, not guessed. That's real signal, but it is not the same as running it. **Treat your first `npm run dev` as the actual test** — the same relationship static code review had to the bugs the live Render deploy surfaced.

**A gap found while scoping this, fixed before writing frontend code:** the backend had no way to *list* submissions or universities — only "fetch one if you already know its ID," which is why the original dashboard made you type in a submission ID by hand. Added:
- `GET /api/submissions` — tenant-scoped list, used by the dashboard
- `GET /api/universities`, `GET /api/universities/{id}/faculties`, `GET /api/universities/{id}/document-types`, `GET /api/universities/{id}/rule-sets` (published only) — reference data the upload form needs to populate its own dropdowns, open to any authenticated principal rather than admin-gated like the existing rule-management endpoints

These three backend files (`universities.py` new, `submissions.py` and `main.py` updated) need to be added to your existing backend repo — they're a small, additive change, not a re-deploy of everything.

**Design direction:** treated as an academic-audit tool rather than a generic SaaS product — a restrained ink-and-paper palette (navy for actions, muted brick/ochre/forest for severity rather than default red/yellow/green), a serif for document-related headings paired with a clean sans for UI chrome, and findings presented as a structured table rather than a stack of shadowed cards.

**What's needed to actually deploy it:** see `DEPLOY.md` in the frontend package — in short, push to its own repo, deploy on Vercel (or any Node host) with `NEXT_PUBLIC_API_BASE_URL` set to the backend's URL, then add that frontend's URL to the backend's `ALLOWED_ORIGINS` so CORS doesn't block it. Not done yet — a next step once you've reviewed the code.

## 8. Real Authentication, PDF Evaluation Reports, and Institutional Redesign

Three more requested pieces, built and verified where verification was possible in this sandbox.

### Real username/password authentication

Not OIDC/SSO (that still needs an actual identity provider account — see the frontend's `AUTH_TODO.md`), but genuinely real: hashed passwords, signed tokens, real database-backed accounts — replacing the client-side role-picker placeholder entirely for anyone who signs in through `/login` now.

- Passwords hashed with PBKDF2-HMAC-SHA256, 260,000 iterations (`app/security/passwords.py`) — deliberately stdlib-only rather than adding `bcrypt`/`passlib` to `requirements.txt`, since this sandbox has no way to verify a new pip dependency installs cleanly before shipping it
- Signed tokens (`app/security/identity.py`) issued on successful login, verified on every request
- **Both directly tested, not just read through**: confirmed correct passwords verify and wrong ones don't; confirmed a token with the wrong signing secret is rejected; confirmed an expired token is rejected
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` (`app/api/auth.py`) — registration is open in demo mode (so you can create accounts for every role to explore with) and admin-gated otherwise
- This also means `User`/`UserRole` — present in the schema since the original handoff but never actually queried by any code — are now genuinely wired up and in use

### PDF evaluation report

Distinct from the compliance certificate (which only exists after a compliant decision): this is the full working evaluation, available at any point in review, compliant or not. Lists every finding with its rule ID, severity, a status "marking" (Non-Compliant / Waived / Resolved / etc. — derived from review status, not just severity, so a waived Major finding reads as resolved rather than as an outstanding failure), expected vs. actual values, and its guideline reference.

That guideline reference required a real fix: the engine has always computed a source reference (e.g. "Annexure 19 p.6") for every finding, but `app/services/processing.py` was discarding it before it ever reached the database. Added `Finding.source_reference` to persist it, and it now shows in both the web findings table and the PDF.

**Verified by actually generating a PDF**, not just written and assumed correct: rendered a real report with realistic fake findings data, confirmed valid PDF structure (magic bytes, EOF marker, page objects), and confirmed the table's column widths fit safely within an A4 page. The SQLAlchemy query portions weren't independently testable in this sandbox (no SQLAlchemy installed here), but follow the exact same pattern as the already-proven, already-working `certificate.py`.

### Institutional visual redesign

Matched Alliance University's actual site's *style* — confirmed navy/blue identity, editorial trust-building layout, accreditation-badge patterns — without using their actual logo or copyrighted photography, which I don't have redistribution rights to. If you have their exact brand colors or logo file, share them and I'll swap in the precise versions.

Concretely: a navy masthead with a real (not fabricated) trust-mark strip — "Annexure 18/19 Rule Coverage," "SHA-256 Version Integrity," "Hash-Chained Audit Trail" — across every authenticated page, and a two-column institutional-portal treatment for `/login` (navy branding panel alongside the sign-in form, similar to how Alliance's own student/faculty login portals are laid out).

### Database migration note for your live demo specifically

`User.password_hash` and `Finding.source_reference` are new columns. Your live Render Postgres already exists with the old schema, and since this deployment runs in `ENVIRONMENT=development` mode (which only calls `create_all()`, not real Alembic migrations), those new columns wouldn't appear automatically. Handled with an automatic, idempotent backfill in `app/main.py`'s startup function — it checks whether each column exists and adds it if not, safe to run on every restart. A real Alembic migration (`alembic/versions/0004_auth_and_source_reference.py`) also exists for when this moves to a deployment that runs migrations for real.

### One more bug caught before shipping: `EmailStr` would have crashed the whole app

While preparing deployment instructions, I checked whether `app/api/auth.py`'s use of Pydantic's `EmailStr` type would actually work — it wouldn't have. `EmailStr` requires a separate `email-validator` package that isn't in `requirements.txt`; Pydantic raises an `ImportError` at import time when it's missing, which would have taken down the *entire* API on next deploy, not just registration (since `main.py` imports this module). Replaced with a plain stdlib regex validation (`app/api/auth.py`), consistent with the same "no untested new dependencies" reasoning already applied to password hashing. Verified the regex logic directly against realistic and malformed email addresses before shipping it.

## 9. Path to the "Proper" Production Web Application

The handoff's own `CLAUDE_HANDOFF_PROMPT.md` lays out eight phases. Here's where each one actually stands after this work:

| Phase | Description | Status |
|---|---|---|
| 1. Understand | Read the repo, run tests, map APIs, identify gaps | **Done** — this report and `PHASE1_FINDINGS.md` |
| 2. Frontend | Production Next.js/React frontend, 20 required screens | **First batch done** — core workflow (login placeholder, dashboard, submission detail) built and type-checked, not yet run or deployed. Admin screens not started. |
| 3. Identity | Real OIDC/OAuth2, remove dev headers from staging/prod | **Not started** — demo and new frontend both run on dev-header identity; `AUTH_TODO.md` documents the exact migration path |
| 4. Infrastructure | IaC for GCP (Cloud Run, Cloud SQL, Cloud Storage, etc.), dev/staging/prod environments | **Partially analogous** — the Render Blueprint demonstrates the *pattern* (declarative infra, one-command deploy) but targets Render, not GCP, and isn't the separated dev/staging/prod setup the docs call for |
| 5. Worker hardening | Isolated worker, resource limits, restricted egress, no app secrets | **Regressed on purpose for the demo** — we removed the worker split entirely to fit free-tier constraints. Production needs it back, properly isolated |
| 6. E2E testing | Automated test: upload → certificate | **Not automated**, but manually verified once, live, in this session |
| 7. Security | SAST/SCA/secrets/container/DAST gates, auth matrix, tenant isolation, malicious-upload and prompt-injection corpora | **Not started** |
| 8. Pilot | Configure Alliance University, import approved rule set, measure accuracy/turnaround before real student use | **Blocked on Phases 2/3/4/7** (rule-catalogue gap now mostly closed — see Section 6) |

### Recommended sequencing

Not all eight phases carry equal weight right now, and some are premature before others:

1. **Rule catalogue: mostly closed.** 49 of 62 rules (79%) implemented and verified against the real thesis, up from 27/62 (44%) at the start of this session. The 13 remaining are each documented above with a specific reason (rendered-PDF-only, needs a schema change, or genuinely not deterministic) rather than left as an unexplained gap.
2. **Production frontend (Phase 2): first batch done.** Core workflow built (Section 7) — not yet run, deployed, or extended to admin screens.
3. **Real OIDC (Phase 3)** should land before any real student data ever touches this, full stop — it's a hard prerequisite for Phase 8, not optional. `AUTH_TODO.md` in the frontend package documents exactly what changes on both sides when this happens.
4. **Infrastructure, worker hardening, and security testing (Phases 4, 5, 7)** matter most once an actual institutional pilot is greenlit — they're about hardening something for real use, and there's limited value doing them against a moving target while the frontend is still catching up.
5. **Pilot (Phase 8)** is the finish line, not a next step.

Each remaining phase (real OIDC, admin frontend screens, infrastructure) is a substantial body of work in its own right. I'd want to scope whichever one you pick next the same way we did this one, rather than starting several at once.

---

## 10. Files Changed in This Work

All delivered as a complete, ready-to-push repository:

- `engine/thesis_compliance_engine_v0_2.py` — Phase 1 regex fix (3 locations), plus Section 6's rule-catalogue additions (22 new/corrected checks)
- `app/services/validator.py` — path fix
- `app/services/inline_processing.py` — new, synchronous validation fallback
- `app/api/submissions.py` — wired to use the fallback when Redis isn't configured
- `app/api/health.py` — new `/api/dev/bootstrap` endpoint for the demo upload form
- `app/main.py` — demo-seed startup hook, root redirect
- `app/config.py` — new `demo_seed` setting
- `app/seed_rules.py` — status fix, new `seed_demo_university_if_empty()`
- `app/db.py` — Postgres connection-string driver auto-correction
- `alembic/env.py` — same driver fix, for future migrations
- `app/security/headers.py` — scoped CSP relaxation for `/review`
- `app/api/universities.py` — new: list universities/faculties/document-types/published rule sets
- `frontend-next/` — new: production Next.js frontend (separate deployment), see its own `README.md`
- `app/models.py` — `User.password_hash`, `Finding.source_reference` columns
- `app/security/passwords.py` — new: password hashing (tested)
- `app/security/identity.py` — self-issued token issuance/verification (tested)
- `app/security/dependencies.py` — `get_principal` now checks real tokens first
- `app/api/auth.py` — new: register/login/me
- `app/services/evaluation_report.py` — new: PDF evaluation report (tested)
- `app/api/evaluation_report.py` — new: its endpoint
- `alembic/versions/0004_auth_and_source_reference.py` — new: real migration for the two new columns
- `app/main.py` — automatic column backfill for the live demo database
- `frontend-next/components/ui.tsx` — new `Masthead` component
- `frontend-next/app/login/page.tsx` — rewritten: real login/register form, two-column institutional layout
- `frontend/index.html` — added upload form and demo-bootstrap wiring
- `Dockerfile` — added `COPY engine`, `COPY frontend`
- `render.yaml` — new, one-file deployment blueprint
