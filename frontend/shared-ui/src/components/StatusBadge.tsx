"use client";

import { cn } from "../lib/cn";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-[var(--rp-info)]/20 text-[var(--rp-info)] border-[var(--rp-info)]/40",
  processing: "bg-[var(--rp-warning)]/20 text-[var(--rp-warning)] border-[var(--rp-warning)]/40",
  indexed: "bg-[var(--rp-success)]/20 text-[var(--rp-success)] border-[var(--rp-success)]/40",
  failed: "bg-[var(--rp-danger)]/20 text-[var(--rp-danger)] border-[var(--rp-danger)]/40",
  deleted: "bg-[var(--rp-text-muted)]/20 text-[var(--rp-text-muted)] border-[var(--rp-border)]",
  active: "bg-[var(--rp-accent-soft)] text-[var(--rp-accent-strong)] border-[var(--rp-accent)]/40",
  inactive: "bg-[var(--rp-bg-muted)] text-[var(--rp-text-muted)] border-[var(--rp-border)]",
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const key = status.toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize tracking-wide",
        STATUS_STYLES[key] || STATUS_STYLES.inactive,
        className,
      )}
    >
      {status}
    </span>
  );
}
