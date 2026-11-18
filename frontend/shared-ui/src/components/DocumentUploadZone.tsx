"use client";

import type { ChangeEvent, DragEvent } from "react";
import { useCallback, useState } from "react";
import { cn } from "../lib/cn";

export function DocumentUploadZone({
  onFiles,
  accept = ".pdf,.md,.docx,.png,.jpg,.jpeg,.txt",
  multiple = true,
  disabled = false,
}: {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
}) {
  const [dragging, setDragging] = useState(false);

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || disabled) return;
      onFiles(Array.from(list));
    },
    [disabled, onFiles],
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "relative rounded-[var(--rp-radius)] border-2 border-dashed px-6 py-10 text-center transition",
        dragging
          ? "border-[var(--rp-accent)] bg-[var(--rp-accent-soft)]"
          : "border-[var(--rp-border)] bg-[var(--rp-bg-elevated)]",
        disabled && "opacity-50 pointer-events-none",
      )}
    >
      <p className="text-[var(--rp-text)] font-medium">Drop documents here</p>
      <p className="mt-1 text-sm text-[var(--rp-text-muted)]">
        PDF, Markdown, DOCX, images — multi-file upload supported
      </p>
      <label className="mt-4 inline-flex cursor-pointer items-center rounded-[var(--rp-radius)] bg-[var(--rp-surface)] px-4 py-2 text-sm text-[var(--rp-text)] border border-[var(--rp-border)] hover:bg-[var(--rp-bg-muted)]">
        Browse files
        <input
          type="file"
          className="sr-only"
          accept={accept}
          multiple={multiple}
          onChange={onChange}
          disabled={disabled}
        />
      </label>
    </div>
  );
}
