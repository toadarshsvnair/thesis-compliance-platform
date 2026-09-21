# Authentication status

## What's real now

`/login` is a genuine username/password system, not a placeholder:
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

## What's still a placeholder

This is **not** OIDC/SSO — it doesn't integrate with Alliance University's
actual identity system (or Google/Microsoft/anything external). It's a
self-contained login this application owns entirely. Specifically still
missing:
- **Account provisioning at scale.** Right now, registration is wide open in
  demo mode (`DEMO_SEED=true`) and admin-gated otherwise — there's no bulk
  import of real student/staff accounts, and no bootstrapping path for a real
  deployment's *first* admin account (would need a one-off database insert
  or script).
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
