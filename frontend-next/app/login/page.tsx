"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login } from "@/lib/api";
import type { Role } from "@/lib/types";
import { setSession } from "@/lib/session";
import { Button } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await login(email, password);
      setSession({
        token: result.access_token,
        userId: String(result.user.id),
        email: result.user.email,
        displayName: result.user.display_name,
        roles: result.user.roles as Role[],
        universityIds: result.user.university_ids,
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Incorrect email or password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6 bg-gradient-to-br from-navy to-navy-deep">
      <div className="w-full max-w-sm bg-panel rounded-lg shadow-xl p-10">
        <div className="text-center mb-8">
          <h1 className="font-serif text-2xl text-ink">Thesis Compliance Platform</h1>
          <p className="text-sm text-muted mt-1">University Thesis Formatting Review</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold tracking-wide text-muted mb-1.5">EMAIL</label>
            <input
              required
              type="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="focus-ring w-full border border-line bg-paper px-3 py-2.5 text-sm rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold tracking-wide text-muted mb-1.5">PASSWORD</label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="focus-ring w-full border border-line bg-paper px-3 py-2.5 text-sm rounded"
            />
          </div>
          {error && <p className="text-sm text-brick">{error}</p>}
          <Button type="submit" disabled={busy} className="w-full !rounded !py-2.5">
            {busy ? "Signing in…" : "Sign In →"}
          </Button>
        </form>

        <p className="text-xs text-muted text-center mt-6">
          Accounts are created by your University Admin.
        </p>
      </div>
    </main>
  );
}
