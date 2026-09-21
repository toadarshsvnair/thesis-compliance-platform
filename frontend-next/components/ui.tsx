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

export function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="relative bg-panel rounded-lg shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h3 className="font-serif text-lg text-ink">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="focus-ring text-muted hover:text-ink text-xl leading-none px-1"
          >
            ×
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="px-5 py-4 border-t border-line flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

const NAV_ITEMS: { href: string; label: string; adminOnly?: boolean }[] = [
  { href: "/dashboard", label: "Submissions" },
  { href: "/admin/users", label: "Manage users", adminOnly: true },
];

/** Persistent left-nav shell used on every authenticated page, replacing a
 * per-page top banner and manual "back to dashboard" links with real
 * cross-page navigation. */
export function AppShell({
  active,
  isAdmin,
  userLabel,
  roleLabel,
  onSignOut,
  onNavigate,
  children,
}: {
  active: string;
  isAdmin: boolean;
  userLabel: string;
  roleLabel: string;
  onSignOut: () => void;
  onNavigate: (href: string) => void;
  children: React.ReactNode;
}) {
  const items = NAV_ITEMS.filter((i) => !i.adminOnly || isAdmin);
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-60 shrink-0 bg-navy-deep text-paper flex md:flex-col justify-between">
        <div className="flex md:flex-col w-full">
          <div className="px-5 py-5">
            <span className="font-serif text-lg leading-tight">Thesis Compliance</span>
          </div>
          <nav className="flex md:flex-col md:mt-2 px-2 gap-1 overflow-x-auto md:overflow-visible">
            {items.map((item) => (
              <button
                key={item.href}
                onClick={() => onNavigate(item.href)}
                className={clsx(
                  "focus-ring text-left px-3 py-2 rounded text-sm whitespace-nowrap transition-colors",
                  active === item.href ? "bg-paper/10 text-paper font-medium" : "text-paper/65 hover:bg-paper/5 hover:text-paper"
                )}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="hidden md:block px-5 py-4 border-t border-paper/10">
          <p className="text-sm text-paper truncate">{userLabel}</p>
          <p className="text-xs text-paper/55 mb-3">{roleLabel}</p>
          <button onClick={onSignOut} className="focus-ring text-xs text-paper/70 hover:text-paper hover:underline underline-offset-2">
            Sign out
          </button>
        </div>
      </aside>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-lg text-ink border-b border-line pb-2 mb-4">{children}</h2>;
}
