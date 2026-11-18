"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../lib/cn";
import { Button } from "./Button";
import { CitationChip, type Citation } from "./CitationChip";

const STATUS_LABELS: Record<string, string> = {
  "searching your documents": "Searching your documents",
  thinking: "Thinking",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status.charAt(0).toUpperCase() + status.slice(1);
}

function StatusIndicator({ status }: { status?: string }) {
  return (
    <div className="flex items-center gap-2 py-0.5">
      <motion.span
        className="text-sm font-medium text-[var(--rp-accent-strong)]"
        animate={{ opacity: [0.55, 1, 0.55] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
      >
        {statusLabel(status || "thinking")}
      </motion.span>
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--rp-accent-strong)]"
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
          />
        ))}
      </span>
    </div>
  );
}

const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-2 last:mb-0">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>
  ),
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-[var(--rp-accent-strong)] underline underline-offset-2"
    >
      {children}
    </a>
  ),
  // react-markdown v9 no longer passes an `inline` flag to `code`, so instead of
  // branching on that, style inline code as a pill and have `pre` strip it back
  // down to plain text for fenced code blocks (see its className below).
  code: ({ children }: { children?: ReactNode }) => (
    <code className="rounded bg-[var(--rp-bg-muted)] px-1 py-0.5 font-mono text-[0.85em]">
      {children}
    </code>
  ),
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="mb-2 overflow-x-auto rounded-[10px] border border-[var(--rp-border)] bg-[var(--rp-bg-muted)] p-3 font-mono text-[0.85em] last:mb-0 [&>code]:bg-transparent [&>code]:p-0">
      {children}
    </pre>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold text-[var(--rp-text)]">{children}</strong>
  ),
};

export function ChatBubble({
  role,
  content,
  citations,
  insufficient,
  isError,
  streaming,
  status,
  onFeedback,
  footer,
}: {
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  insufficient?: boolean;
  isError?: boolean;
  streaming?: boolean;
  status?: string;
  onFeedback?: (rating: "up" | "down") => void;
  footer?: ReactNode;
}) {
  const isUser = role === "user";
  const showTyping = !isUser && streaming && !content;

  return (
    <motion.div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <div
        className={cn(
          "max-w-[min(720px,92%)] rounded-[14px] px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-[var(--rp-accent-strong)] text-[#04201c]"
            : isError
              ? "border border-[var(--rp-danger)]/50 bg-[var(--rp-danger)]/10 text-[var(--rp-text)]"
              : insufficient
                ? "border border-[var(--rp-warning)]/50 bg-[var(--rp-warning)]/10 text-[var(--rp-text)]"
                : "border border-[var(--rp-border)] bg-[var(--rp-bg-elevated)] text-[var(--rp-text)]",
        )}
      >
        {isError && (
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--rp-danger)]">
            Something went wrong
          </p>
        )}
        {insufficient && !isError && (
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--rp-warning)]">
            Insufficient information
          </p>
        )}
        {showTyping ? (
          <StatusIndicator status={status} />
        ) : isUser || streaming ? (
          <div className="whitespace-pre-wrap">
            {content}
            {streaming && <span className="ml-0.5 inline-block animate-pulse">▍</span>}
          </div>
        ) : (
          <div className="[&>*:last-child]:mb-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {content}
            </ReactMarkdown>
          </div>
        )}
        {!isUser && citations && citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {citations.map((c, i) => (
              <CitationChip key={`${c.doc_id}-${i}`} citation={c} index={i} />
            ))}
          </div>
        )}
        {!isUser && onFeedback && !streaming && content && !isError && (
          <div className="mt-3 flex gap-2">
            <Button type="button" variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onFeedback("up")}>
              👍
            </Button>
            <Button type="button" variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onFeedback("down")}>
              👎
            </Button>
          </div>
        )}
        {footer}
      </div>
    </motion.div>
  );
}
