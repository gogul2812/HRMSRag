"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary:
    "bg-[var(--rp-accent-strong)] text-[#04201c] hover:brightness-110 font-semibold",
  secondary:
    "bg-[var(--rp-surface)] text-[var(--rp-text)] border border-[var(--rp-border)] hover:bg-[var(--rp-bg-muted)]",
  ghost: "bg-transparent text-[var(--rp-text-muted)] hover:text-[var(--rp-text)] hover:bg-[var(--rp-bg-muted)]",
  danger: "bg-[var(--rp-danger)] text-white hover:brightness-110",
};

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: Variant;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--rp-radius)] px-4 py-2 text-sm transition disabled:opacity-50 disabled:cursor-not-allowed",
        styles[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
