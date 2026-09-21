"use client";

import { ButtonHTMLAttributes } from "react";
import clsx from "clsx";

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  return (
    <button
      className={clsx(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        variant === "primary" && "bg-navy text-paper hover:bg-navy-deep",
        variant === "secondary" && "border border-line bg-panel text-ink hover:border-navy/40",
        variant === "danger" && "border border-brick/40 bg-panel text-brick hover:bg-brick/5",
        variant === "ghost" && "text-navy hover:underline underline-offset-2",
        className
      )}
      {...props}
    />
  );
}

const SEVERITY_STYLE: Record<string, string> = {
  Critical: "border-brick/50 text-brick bg-brick/5",
  Major: "border-brick/40 text-brick bg-brick/5",
  Review: "border-navy/40 text-navy bg-navy/5",
  Minor: "border-ochre/50 text-ochre bg-ochre/10",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={clsx(
        "inline-block rounded-sm border px-2 py-0.5 text-xs font-medium",
        SEVERITY_STYLE[severity] ?? "border-line text-muted"
      )}
    >
      {severity}
    </span>
  );
}

const STATUS_STYLE: Record<string, string> = {
  open: "border-line text-muted",
  reviewed: "border-navy/40 text-navy bg-navy/5",
  waived: "border-ochre/50 text-ochre bg-ochre/10",
  rejected: "border-brick/40 text-brick bg-brick/5",
  fix_approved: "border-forest/40 text-forest bg-forest/5",
  fixed: "border-forest/50 text-forest bg-forest/10",
  revalidation_failed: "border-brick/50 text-brick bg-brick/10",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-block rounded-sm border px-2 py-0.5 text-xs font-medium capitalize",
        STATUS_STYLE[status] ?? "border-line text-muted"
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("border border-line bg-panel", className)}>{children}</div>;
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-lg text-ink border-b border-line pb-2 mb-4">{children}</h2>;
}

const TRUST_MARKS = [
  "Annexure 18 / 19 Rule Coverage",
  "SHA-256 Version Integrity",
  "Hash-Chained Audit Trail",
  "Human-Gated Compliance Decision",
];

/** The top masthead used on every authenticated page — an institutional-portal
 * treatment (navy bar, trust-mark strip) rather than a plain page title. The
 * trust marks are real, verifiable properties of this platform, not
 * accreditation claims. */
export function Masthead({ subtitle, right }: { subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="bg-navy text-paper">
      <div className="max-w-5xl mx-auto px-6 py-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-[11px] tracking-[0.14em] text-gold font-medium mb-1">UNIVERSITY THESIS REVIEW</p>
          <h1 className="font-serif text-2xl leading-tight">Thesis Compliance Platform</h1>
          {subtitle && <p className="text-sm text-paper/70 mt-1">{subtitle}</p>}
        </div>
        {right}
      </div>
      <div className="border-t border-paper/10">
        <div className="max-w-5xl mx-auto px-6 py-2.5 flex flex-wrap gap-x-6 gap-y-1">
          {TRUST_MARKS.map((mark) => (
            <span key={mark} className="text-[11px] text-paper/60 flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-gold" />
              {mark}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
