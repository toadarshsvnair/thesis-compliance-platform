# Replacing the placeholder login with real OIDC

Today, `/login` lets anyone pick a role and university ID, store it in
`localStorage`, and have every API call send it as `X-User-*` headers — this
mirrors the backend's own dev-mode header authentication
(`app/security/dependencies.py`), which only exists for local development
and explicitly refuses to run this way once `ENVIRONMENT` is `production` or
`staging`. Neither half of this is a real access control.

## What changes, and what doesn't

The API client's call sites (every function in `lib/api.ts`) don't need to
change at all — they already just call `sessionHeaders(session)` to get
whatever headers to attach. Only two things need to change:

1. **`lib/session.ts`** — instead of reading/writing `localStorage`, this
   becomes "get the current user's ID token from the OIDC provider's SDK"
   (e.g. NextAuth.js, Auth0's Next.js SDK, or a hand-rolled
   `next-auth`-style flow against your chosen identity provider).
2. **The header shape itself** — `sessionHeaders()` currently builds
   `X-User-Id` / `X-User-Roles` / etc. Once the backend's OIDC path is live
   (`app/security/identity.py`'s `principal_from_jwt`), this becomes a
   single `Authorization: Bearer <id_token>` header instead, and the
   role/university claims come from the token itself, not from the
   frontend's own state.

## Sequencing with the backend

This can't land in the frontend alone — it depends on:
- An actual identity provider being chosen and configured (Google
  Workspace, Azure AD, Auth0, Keycloak, or similar) with real client
  credentials.
- `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, and `OIDC_REQUIRED=true`
  set on the backend (`app/config.py` already has these settings; they're
  just unset in the demo deployment).
- A decision on how roles map from the identity provider's claims to this
  app's four roles (student / research_officer / university_admin /
  super_admin) — the backend's `principal_from_jwt` already reads a `roles`
  claim and a `realm_access.roles` claim (Keycloak-style), but whichever
  provider gets chosen needs to actually populate one of those.

None of that is a frontend decision to make alone.
