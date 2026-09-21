from dataclasses import dataclass
from typing import Optional
import json
import time
import urllib.request
import jwt
from jwt import PyJWKClient

SELF_ISSUED_ISSUER = "thesis-compliance-platform-self-issued"

@dataclass(frozen=True)
class Principal:
    subject: str
    email: str
    roles: frozenset[str]
    university_ids: frozenset[int]

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


def principal_from_dev_headers(x_user_id, x_user_email, x_user_roles, x_university_ids) -> Principal:
    roles = frozenset(r.strip() for r in (x_user_roles or "").split(",") if r.strip())
    universities = frozenset(int(x.strip()) for x in (x_university_ids or "").split(",") if x.strip().isdigit())
    return Principal(x_user_id or "development-user", x_user_email or "development@example.invalid", roles, universities)


def issue_self_signed_token(secret_key: str, subject: str, email: str, roles: list[str],
                             university_ids: list[int], expires_in_seconds: int = 12 * 3600) -> str:
    """Issue our own HS256 JWT after a successful username/password login.
    This is real, cryptographically-signed authentication -- distinct from
    both the dev-header placeholder and third-party OIDC. It's the practical
    middle ground: no external identity provider to configure, but a real
    login with real, hashed, server-verified credentials behind it."""
    now = int(time.time())
    payload = {
        "iss": SELF_ISSUED_ISSUER,
        "sub": subject,
        "email": email,
        "roles": roles,
        "university_ids": university_ids,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def principal_from_self_issued_jwt(token: str, secret_key: str) -> Principal:
    claims = jwt.decode(
        token, secret_key, algorithms=["HS256"],
        issuer=SELF_ISSUED_ISSUER,
        options={"require": ["sub", "iss", "exp"]},
    )
    roles = frozenset(claims.get("roles", []))
    universities = frozenset(int(x) for x in claims.get("university_ids", []) if str(x).lstrip("-").isdigit())
    return Principal(str(claims["sub"]), str(claims.get("email", "")), roles, universities)


def principal_from_jwt(token: str, issuer: str, audience: str, jwks_url: str) -> Principal:
    if not all([issuer, audience, jwks_url]):
        raise ValueError("OIDC issuer, audience and JWKS URL must be configured.")
    client = PyJWKClient(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    claims = jwt.decode(token, signing_key.key, algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"], audience=audience, issuer=issuer, options={"require": ["sub", "iss", "aud", "exp"]})
    roles = set(claims.get("roles", []))
    if isinstance(claims.get("realm_access"), dict):
        roles.update(claims["realm_access"].get("roles", []))
    universities = set()
    for value in claims.get("university_ids", []):
        try: universities.add(int(value))
        except (TypeError, ValueError): pass
    return Principal(str(claims["sub"]), str(claims.get("email", "")), frozenset(roles), frozenset(universities))
