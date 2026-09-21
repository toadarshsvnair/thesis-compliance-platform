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
