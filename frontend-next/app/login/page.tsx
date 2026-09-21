"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getDevBootstrap } from "@/lib/api";
import { ROLE_LABELS, setSession } from "@/lib/session";
import type { Role } from "@/lib/types";
import { Button } from "@/components/ui";

const ROLE_ORDER: Role[] = ["research_officer", "university_admin", "student", "super_admin"];

export default function LoginPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("research_officer");
  const [universityIds, setUniversityIds] = useState("1");
  const [name, setName] = useState("");
  const [demoLabel, setDemoLabel] = useState<string | null>(null);

  useEffect(() => {
    getDevBootstrap().then((bootstrap) => {
      if (bootstrap) {
        setUniversityIds(String(bootstrap.university_id));
        setDemoLabel(bootstrap.university_name);
      }
    });
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ids = universityIds
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !Number.isNaN(n));
    setSession({
      userId: name.trim() ? name.trim().toLowerCase().replace(/\s+/g, "-") : `${role}-dev`,
      email: name.trim() ? `${name.trim().toLowerCase().replace(/\s+/g, ".")}@example.edu` : `${role}@example.edu`,
      roles: [role],
      universityIds: ids,
    });
    router.replace("/dashboard");
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <h1 className="font-serif text-3xl text-ink mb-1">Thesis Compliance Platform</h1>
        <p className="text-muted text-sm mb-8">Formatting compliance review for university theses</p>

        <div className="border border-ochre/40 bg-ochre/5 text-sm text-ink px-4 py-3 mb-6">
          <strong className="font-medium">Placeholder identity, not real sign-in.</strong> This
          deployment has no identity provider configured yet — choose a role to explore the
          workflow with. See <code className="text-xs">AUTH_TODO.md</code> for the real-OIDC plan.
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">Your name (optional)</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Reviewer"
              className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">Role</label>
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

          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              University ID{demoLabel ? ` — ${demoLabel}` : ""}
            </label>
            <input
              value={universityIds}
              onChange={(e) => setUniversityIds(e.target.value)}
              placeholder="1"
              className="focus-ring w-full border border-line bg-panel px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted mt-1">Comma-separate multiple IDs. Super Admin ignores this.</p>
          </div>

          <Button type="submit" className="w-full">
            Continue
          </Button>
        </form>
      </div>
    </main>
  );
}
