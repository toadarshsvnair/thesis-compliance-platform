"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession } from "./session";
import type { Session } from "./types";

/** Redirects to /login if there's no session; otherwise returns it once loaded.
 * `session` is `undefined` while still checking (avoids a login-page flash),
 * and `null` only for the instant before the redirect takes effect. */
export function useRequireSession(): Session | undefined {
  const router = useRouter();
  const [session, setSession] = useState<Session | undefined>(undefined);

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    setSession(s);
  }, [router]);

  return session;
}
