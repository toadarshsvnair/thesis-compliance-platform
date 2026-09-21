# Thesis Compliance Platform — Frontend

Production Next.js frontend for the Thesis Compliance Platform backend. This
is a separate deployment from the backend (a different runtime — Node vs.
Python — can't share a Render service), talking to it over the network as a
regular API client.

**This was written but never run in a real Node environment** — the sandbox
that built it has no network access to install `next`/`react`/etc. from npm.
It was type-checked in strict mode against the real `react`/`typescript`
packages with zero errors, and every API call is written against the exact
backend response shapes (see `lib/types.ts`, cross-referenced directly
against the FastAPI route handlers). But "type-checks cleanly" is not the
same as "runs correctly" — treat the first `npm run dev` as the real test,
the same way the first Render deploy surfaced real issues static review
didn't catch. Report back whatever breaks and it'll get fixed the same way.

## Local development

```bash
npm install
cp .env.example .env.local
# edit .env.local: set NEXT_PUBLIC_API_BASE_URL to your deployed backend's URL
npm run dev
```

Open http://localhost:3000 — it redirects to `/login`.

## What's here

- `/login` — placeholder dev-mode sign-in (pick a role + university; there is
  no real identity provider yet). See `AUTH_TODO.md`.
- `/dashboard` — lists submissions for your role/university, and a form to
  create a new one (with dropdowns for university/faculty/document
  type/rule set, populated live from the backend).
- `/submissions/[id]` — the review workspace: findings (with review actions
  and controlled auto-fix preview/apply for reviewer roles), version
  history and comparison, audit trail, and the human compliance decision
  with certificate generation.

## What's not here yet

Per the platform's own 20-screen frontend spec (`CLAUDE_HANDOFF_PROMPT.md`),
this covers the core submission/review workflow only. Not yet built:
university/faculty/document-type/rule-set administration screens, guideline
source management, and dedicated security/admin operations screens — all of
which map to backend endpoints that already exist (`/api/rule-management/*`)
but have no frontend yet. A reasonable second batch.

## Deployment

See `DEPLOY.md`.
