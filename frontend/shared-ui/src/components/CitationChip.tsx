"use client";

import { cn } from "../lib/cn";

export type Citation = {
  doc_id: string;
  chunk_index?: number | null;
  section?: string | null;
  page?: number | null;
  score?: number | null;
  excerpt?: string;
};

export function CitationChip({
  citation,
  index,
  onClick,
}: {
  citation: Citation;
  index?: number;
  onClick?: () => void;
}) {
  const label = [
    citation.section || `Source ${(index ?? 0) + 1}`,
    citation.page != null ? `p.${citation.page}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      title={citation.excerpt || citation.doc_id}
      onClick={onClick}
      className={cn(
        "inline-flex max-w-full items-center rounded-full border border-[var(--rp-border)]",
        "bg-[var(--rp-bg-muted)] px-2.5 py-1 text-xs text-[var(--rp-text-muted)]",
        "hover:border-[var(--rp-accent)] hover:text-[var(--rp-accent-strong)]",
      )}
    >
      <span className="truncate">{label}</span>
    </button>
  );
}
