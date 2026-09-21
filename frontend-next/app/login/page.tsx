"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, getDevBootstrap, login, register } from "@/lib/api";
import { ROLE_LABELS, setSession } from "@/lib/session";
import type { Role } from "@/lib/types";
import { Button } from "@/components/ui";

const ROLE_ORDER: Role[] = ["research_officer", "university_admin", "student", "super_admin"];

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("research_officer");
  const [universityId, setUniversityId] = useState("1");
  const [demoLabel, setDemoLabel] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getDevBootstrap().then((bootstrap) => {
      if (bootstrap) {
        setUniversityId(String(bootstrap.university_id));
        setDemoLabel(bootstrap.university_name);
        setIsDemo(true);
      }
    });
  }, []);

  async function handleLogin(e: React.FormEvent) {
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
      setError(err instanceof ApiError ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await register({
        email,
        password,
        displayName,
        role,
        universityId: Number(universityId),
      });
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
      setError(err instanceof ApiError ? err.message : "Account creation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-[38%] bg-navy text-paper flex-col justify-between p-12">
        <div>
          <p className="text-[11px] tracking-[0.14em] text-gold font-medium mb-2">UNIVERSITY THESIS REVIEW</p>
          <h1 className="font-serif text-4xl leading-tight">Thesis<br />Compliance<br />Platform</h1>
        </div>
        <div className="space-y-4">
          <p className="text-sm text-paper/70 leading-relaxed max-w-xs">
            Deterministic formatting review against approved institutional guidelines, with a
            human-gated decision on every submission.
          </p>
          <ul className="space-y-2 text-sm text-paper/80">
            {["Annexure 18 / 19 rule coverage", "SHA-256 version integrity", "Hash-chained audit trail"].map((m) => (
              <li key={m} className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-gold" />
                {m}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8">
            <h1 className="font-serif text-3xl text-ink mb-1">Thesis Compliance Platform</h1>
            <p className="text-muted text-sm">Formatting compliance review for university theses</p>
          </div>

          <h2 className="font-serif text-2xl text-ink mb-6">{mode === "login" ? "Sign in" : "Create your account"}</h2>

        <div className="border border-navy/30 bg-navy/5 text-sm text-ink px-4 py-3 mb-6">
          Sign-in here is this platform's own account system — real, hashed
          credentials, not a role picker. It is not yet connected to the
          university's single sign-on; see <code className="text-xs">AUTH_TODO.md</code> for
          that plan.
          {isDemo && (
            <>
              {" "}Registration is open in this demo deployment so you can explore
              every role — a real deployment would restrict account creation to
              administrators.
            </>
          )}
        </div>

        <div className="flex border-b border-line mb-6">
          <button
            className={`flex-1 py-2 text-sm font-medium focus-ring ${mode === "login" ? "border-b-2 border-navy text-navy" : "text-muted"}`}
            onClick={() => setMode("login")}
          >
            Sign in
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium focus-ring ${mode === "register" ? "border-b-2 border-navy text-navy" : "text-muted"}`}
            onClick={() => setMode("register")}
          >
            Create account
          </button>
        </div>

        {mode === "login" ? (
          <form onSubmit={handleLogin} className="space-y-5">
            <Field label="Email">
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Password">
              <input
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            {error && <p className="text-sm text-brick">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="space-y-5">
            <Field label="Full name">
              <input
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Email">
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Password (min. 8 characters)">
              <input
                required
                minLength={8}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            <div>
              <span className="block text-sm font-medium text-ink mb-1.5">Role</span>
              <div className="grid grid-cols-2 gap-2">
                {ROLE_ORDER.map((r) => (
                  <button
                    type="button"
                    key={r}
                    onClick={() => setRole(r)}
                    className={`focus-ring border px-3 py-2 text-sm text-left transition-colors ${
                      role === r ? "border-navy bg-navy/5 text-navy" : "border-line text-ink hover:border-navy/40"
                    }`}
                  >
                    {ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
            </div>
            <Field label={`University ID${demoLabel ? ` — ${demoLabel}` : ""}`}>
              <input
                required
                value={universityId}
                onChange={(e) => setUniversityId(e.target.value)}
                className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
              />
            </Field>
            {error && <p className="text-sm text-brick">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Creating account…" : "Create account"}
            </Button>
          </form>
        )}
        </div>
      </div>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-ink mb-1.5">{label}</span>
      {children}
    </label>
  );
}
