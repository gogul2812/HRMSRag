"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, Button, StatusBadge, formatDate } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";
import { SAMPLE_GUARDRAILS } from "@/lib/samples";
import type { GuardrailPolicy } from "@/lib/types";

type Draft = {
  refuse_topics: string;
  required_disclaimer: string;
  blocked_phrases: string;
  enable_faithfulness_check: boolean;
};

const emptyDraft: Draft = {
  refuse_topics: "",
  required_disclaimer: "",
  blocked_phrases: "",
  enable_faithfulness_check: false,
};

function toDraft(policy?: GuardrailPolicy): Draft {
  if (!policy) return emptyDraft;
  const j = policy.policy_json || {};
  return {
    refuse_topics: (j.refuse_topics || []).join(", "),
    required_disclaimer: j.required_disclaimer || "",
    blocked_phrases: (j.blocked_phrases || []).join(", "),
    enable_faithfulness_check: Boolean(j.enable_faithfulness_check),
  };
}

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function GuardrailsPage() {
  const [versions, setVersions] = useState<GuardrailPolicy[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api.get<GuardrailPolicy[]>(
        "/api/v1/config/guardrails/versions",
      );
      setVersions(rows);
      const active = rows.find((r) => r.is_active);
      if (active) setDraft(toDraft(active));
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setVersions([]);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Failed to load guardrails");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      const policy_json = {
        refuse_topics: parseList(draft.refuse_topics),
        required_disclaimer: draft.required_disclaimer.trim() || undefined,
        blocked_phrases: parseList(draft.blocked_phrases),
        enable_faithfulness_check: draft.enable_faithfulness_check,
      };
      const created = await api.post<GuardrailPolicy>("/api/v1/config/guardrails", {
        policy_json,
      });
      await api.put(`/api/v1/config/guardrails/${created.id}/activate`);
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
      await api.put(`/api/v1/config/guardrails/${id}/activate`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Activate failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold">Guardrails</h2>
        <p className="mt-1 text-sm text-mute">
          Refusal topics, required disclaimers, and blocked phrases for this tenant.
        </p>
      </header>

      <section className="space-y-4 rounded-[14px] border border-line bg-elevated/70 p-5">
        <label className="block text-sm">
          <span className="text-mute">Refuse topics (comma-separated)</span>
          <input
            value={draft.refuse_topics}
            onChange={(e) => setDraft({ ...draft, refuse_topics: e.target.value })}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
            placeholder="competitors, medical advice"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Required disclaimer</span>
          <textarea
            value={draft.required_disclaimer}
            onChange={(e) =>
              setDraft({ ...draft, required_disclaimer: e.target.value })
            }
            rows={3}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
            placeholder="— Internal use only."
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Blocked phrases (comma-separated)</span>
          <input
            value={draft.blocked_phrases}
            onChange={(e) => setDraft({ ...draft, blocked_phrases: e.target.value })}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.enable_faithfulness_check}
            onChange={(e) =>
              setDraft({ ...draft, enable_faithfulness_check: e.target.checked })
            }
            className="mt-1"
          />
          <span>
            <span className="block">AI answer fact-check</span>
            <span className="block text-xs text-mute">
              Runs a second AI call to verify every answer against the source
              documents before showing it. Off by default because it roughly
              doubles cost and response time for every question — turn on only
              if that trade-off is worth it for this tenant.
            </span>
          </span>
        </label>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void publish()} disabled={busy}>
            Publish & activate
          </Button>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() =>
              setDraft({
                refuse_topics: SAMPLE_GUARDRAILS.refuse_topics,
                required_disclaimer: SAMPLE_GUARDRAILS.required_disclaimer,
                blocked_phrases: SAMPLE_GUARDRAILS.blocked_phrases,
                enable_faithfulness_check: false,
              })
            }
          >
            Load sample (Demo Corp)
          </Button>
        </div>
        {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}
      </section>

      <section className="overflow-hidden rounded-[14px] border border-line bg-elevated/70">
        <div className="border-b border-line px-5 py-3 text-sm text-mute">Version history</div>
        <ul className="divide-y divide-line">
          {versions.length === 0 && (
            <li className="px-5 py-8 text-sm text-mute">No policies yet.</li>
          )}
          {versions.map((v) => (
            <li
              key={v.id}
              className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium">Version {v.version}</p>
                <p className="mt-1 text-xs text-mute">{formatDate(v.created_at)}</p>
                <pre className="mt-2 max-w-xl overflow-x-auto rounded bg-canvas p-2 font-mono text-xs text-mute">
                  {JSON.stringify(v.policy_json, null, 2)}
                </pre>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={v.is_active ? "active" : "inactive"} />
                {!v.is_active && (
                  <Button variant="secondary" disabled={busy} onClick={() => void activate(v.id)}>
                    Activate
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setDraft(toDraft(v))}>
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
