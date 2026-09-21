# Authentication status

## What's real now

`/login` is a genuine username/password system, not a placeholder — sign-in
only; there is no self-registration in the UI. Accounts are provisioned by an
existing University Admin or Super Admin (`POST /api/auth/register`, admin-
gated, no UI screen for it yet — call it directly for now, see below).

- Passwords are hashed with PBKDF2-HMAC-SHA256 (260,000 iterations), never
  stored or logged in plain text (`app/security/passwords.py`).
- A successful login gets a real, signed token (`app/security/identity.py`'s
  `issue_self_signed_token`) — HS256, signed with the backend's `SECRET_KEY`,
  12-hour expiry, containing the user's actual roles and university IDs from
  the database (`app/models.py`'s `User`/`UserRole`, previously unused
  scaffolding — nothing in the app queried them before this).
- `app/security/dependencies.py`'s `get_principal` verifies that token on
  every request. Wrong signature or expired token is rejected — both were
  tested directly (not just read through) before this shipped.
- The old dev-header placeholder (`X-User-*`) still exists as a fallback for
  local development convenience, but a real bearer token now takes priority
  whenever one is presented, in every environment.

## The bootstrapping problem, and how it's solved here

Since account creation always requires an existing admin, a brand-new
database has nobody who can create the first account. Solved with automatic
seeding: on startup, if `DEMO_ADMIN_PASSWORD` is set and no user exists yet,
one Super Admin account is created (`app/seed_rules.py`'s
`seed_demo_admin_if_configured`). `render.yaml` generates this password as a
real secret (`generateValue: true`, same pattern as `SECRET_KEY`) — check the
Render dashboard's Environment tab for the actual value, never a hardcoded
default in the code.

## Creating accounts for other people (no UI screen yet)

Once signed in as the seeded admin, create other accounts via the API
directly (a proper "Admin: Create User" screen is a reasonable next addition,
not built yet):
```
curl -X POST https://your-backend-url.onrender.com/api/auth/register \
  -H "Authorization: Bearer <your-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"email":"officer@example.edu","password":"a-real-password","display_name":"Jane Officer","role":"research_officer","university_id":1}'
```
Get `<your-admin-token>` from the browser: after logging in, open dev tools
→ Application/Storage → Local Storage → the `thesis-compliance-dev-session`
key → copy the `token` field's value.

## What's still a placeholder

This is **not** OIDC/SSO — it doesn't integrate with Alliance University's
actual identity system (or Google/Microsoft/anything external). It's a
self-contained login this application owns entirely. Specifically still
missing:
- **Bulk account provisioning.** Creating accounts one at a time via the API
  works, but there's no CSV import or similar for onboarding a whole class or
  department at once, and no "Admin: Create User" screen in the frontend yet.
- **Password reset / forgot-password flow.** Doesn't exist yet.
- **True single sign-on**, if the university wants people to use their
  existing university credentials rather than a separate password for this
  tool specifically.

## If/when real OIDC/SSO is wanted later

`get_principal` already has a code path for it (`principal_from_jwt` in
`identity.py`, validated against `OIDC_ISSUER`/`OIDC_AUDIENCE`/`OIDC_JWKS_URL`)
— it's been there since the original handoff, just never wired to a real
provider. Both auth methods can coexist (self-issued tokens for accounts
created here, OIDC tokens for SSO'd-in accounts) since `get_principal` already
tries self-issued first and falls back to OIDC. Adding it means:
1. Choosing and configuring an actual identity provider (Google Workspace,
   Azure AD, Auth0, Keycloak, etc.) with real client credentials.
2. Setting `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` on the backend.
3. On the frontend: swapping `/login`'s form for whatever redirect flow the
   chosen provider uses (this is the part that actually changes — the API
   client's call sites in `lib/api.ts` don't need to change either way, they
   just call `sessionHeaders(session)` regardless of how the token was
   obtained).
