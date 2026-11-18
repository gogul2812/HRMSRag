"use client";

import { useEffect, useState } from "react";
import { ApiError, StatusBadge } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";
import type { DocumentRow, PromptConfig, GuardrailPolicy } from "@/lib/types";

export default function DashboardPage() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [prompt, setPrompt] = useState<PromptConfig | null>(null);
  const [guardrails, setGuardrails] = useState<GuardrailPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [d] = await Promise.all([
          api.get<DocumentRow[]>("/api/v1/ingest/documents"),
        ]);
        setDocs(d);
        try {
          setPrompt(await api.get<PromptConfig>("/api/v1/config/prompt"));
        } catch {
          setPrompt(null);
        }
        try {
          setGuardrails(await api.get<GuardrailPolicy>("/api/v1/config/guardrails"));
        } catch {
          setGuardrails(null);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
      }
    }
    void load();
  }, []);

  const counts = {
    total: docs.length,
    indexed: docs.filter((d) => d.status === "indexed").length,
    processing: docs.filter((d) =>
      ["pending", "processing"].includes(d.status),
    ).length,
    failed: docs.filter((d) => d.status === "failed").length,
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="mt-1 text-sm text-mute">
          Ingestion overview and active configuration for this tenant.
        </p>
      </header>

      {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Total docs", counts.total],
          ["Indexed", counts.indexed],
          ["In flight", counts.processing],
          ["Failed", counts.failed],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            className="rounded-[14px] border border-line bg-elevated/70 px-5 py-4"
          >
            <p className="text-xs uppercase tracking-wide text-mute">{label}</p>
            <p className="mt-2 text-3xl font-semibold">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-[14px] border border-line bg-elevated/70 p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Active rules</h3>
            {prompt ? (
              <StatusBadge status="active" />
            ) : (
              <StatusBadge status="inactive" />
            )}
          </div>
          <p className="mt-3 text-sm text-mute">
            {prompt
              ? `Version ${prompt.version}`
              : "No active prompt — publish one under Rules."}
          </p>
          {prompt && (
            <p className="mt-2 line-clamp-4 text-sm text-ink">{prompt.text}</p>
          )}
        </div>
        <div className="rounded-[14px] border border-line bg-elevated/70 p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Active guardrails</h3>
            {guardrails ? (
              <StatusBadge status="active" />
            ) : (
              <StatusBadge status="inactive" />
            )}
          </div>
          <p className="mt-3 text-sm text-mute">
            {guardrails
              ? `Version ${guardrails.version}`
              : "No active policy — publish one under Guardrails."}
          </p>
          {guardrails && (
            <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 font-mono text-xs text-mute">
              {JSON.stringify(guardrails.policy_json, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
