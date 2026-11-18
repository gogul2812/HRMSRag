"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, Button, ChatBubble, StatusBadge, formatDate } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";
import { SAMPLE_RULES } from "@/lib/samples";
import type { PromptConfig } from "@/lib/types";

export default function RulesPage() {
  const [versions, setVersions] = useState<PromptConfig[]>([]);
  const [draft, setDraft] = useState("");
  const [previewQuery, setPreviewQuery] = useState(
    "What tech stack does Project Phoenix use?",
  );
  const [previewAnswer, setPreviewAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api.get<PromptConfig[]>("/api/v1/config/prompt/versions");
      setVersions(rows);
      const active = rows.find((r) => r.is_active);
      if (active && !draft) setDraft(active.text);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setVersions([]);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Failed to load rules");
    }
  }, [draft]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function publish() {
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<PromptConfig>("/api/v1/config/prompt", {
        text: draft,
      });
      await api.put(`/api/v1/config/prompt/${created.id}/activate`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  async function activate(id: string) {
    setBusy(true);
    try {
      await api.put(`/api/v1/config/prompt/${id}/activate`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Activate failed");
    } finally {
      setBusy(false);
    }
  }

  async function preview() {
    setBusy(true);
    setPreviewAnswer(null);
    setError(null);
    try {
      const result = await api.post<{ answer: string }>(
        "/api/v1/orchestrate/generate",
        {
          query: previewQuery,
          system_prompt_override: draft,
          chunks: [
            {
              text: "Project Phoenix uses FastAPI, PostgreSQL 16, and Qdrant for the EHR migration staffing study.",
              doc_id: "00000000-0000-0000-0000-000000000099",
              doc_type: "project",
              chunk_index: 0,
              section: "Overview",
              page: 1,
              score: 0.9,
            },
          ],
        },
      );
      setPreviewAnswer(result.answer);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold">Rules</h2>
        <p className="mt-1 text-sm text-mute">
          Versioned system prompt for the tenant agent. Publish activates a new version.
        </p>
      </header>

      <section className="space-y-3 rounded-[14px] border border-line bg-elevated/70 p-5">
        <label className="block text-sm">
          <span className="text-mute">Draft rules</span>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={12}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 font-mono text-sm outline-none focus:border-accent"
            placeholder="You are a helpful enterprise assistant…"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void publish()} disabled={busy || !draft.trim()}>
            Publish & activate
          </Button>
          <Button
            variant="secondary"
            onClick={() => setDraft(SAMPLE_RULES)}
            disabled={busy}
          >
            Load sample (leave / WFH / Phoenix)
          </Button>
          <Button variant="secondary" onClick={() => void preview()} disabled={busy || !draft.trim()}>
            Preview with test question
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
          <input
            value={previewQuery}
            onChange={(e) => setPreviewQuery(e.target.value)}
            className="rounded-[10px] border border-line bg-canvas px-3 py-2 text-sm outline-none focus:border-accent"
            placeholder="Test question"
          />
        </div>
        {previewAnswer && (
          <ChatBubble role="assistant" content={previewAnswer} />
        )}
        {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}
      </section>

      <section className="overflow-hidden rounded-[14px] border border-line bg-elevated/70">
        <div className="border-b border-line px-5 py-3 text-sm text-mute">Version history</div>
        <ul className="divide-y divide-line">
          {versions.length === 0 && (
            <li className="px-5 py-8 text-sm text-mute">No versions yet — publish a draft.</li>
          )}
          {versions.map((v) => (
            <li
              key={v.id}
              className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium">Version {v.version}</p>
                <p className="mt-1 text-xs text-mute">{formatDate(v.created_at)}</p>
                <p className="mt-2 max-w-xl truncate text-sm text-mute">{v.text}</p>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={v.is_active ? "active" : "inactive"} />
                {!v.is_active && (
                  <Button variant="secondary" disabled={busy} onClick={() => void activate(v.id)}>
                    Activate
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setDraft(v.text)}>
                  Load
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
