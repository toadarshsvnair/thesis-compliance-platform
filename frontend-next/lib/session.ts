"use client";

// There is no real identity provider yet -- the backend authenticates via
// X-User-* headers outside of production/staging (see
// app/security/dependencies.py). This module is the frontend half of that
// same placeholder: it lets someone pick a role and university, stores that
// choice, and every API call attaches it as headers. Swap this out (not the
// API client's *call sites*, just how it gets its headers) once real OIDC
// exists -- see AUTH_TODO.md at the project root for the specific plan.

import type { Role, Session } from "./types";

const STORAGE_KEY = "thesis-compliance-dev-session";

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function setSession(session: Session): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function sessionHeaders(session: Session): Record<string, string> {
  return { Authorization: `Bearer ${session.token}` };
}

export const ROLE_LABELS: Record<Role, string> = {
  student: "Student",
  research_officer: "Research Officer",
  university_admin: "University Admin",
  super_admin: "Super Admin",
};

export function hasRole(session: Session | null, ...roles: Role[]): boolean {
  if (!session) return false;
  return session.roles.some((r) => roles.includes(r));
}
