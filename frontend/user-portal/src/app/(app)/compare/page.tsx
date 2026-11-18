"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  Button,
  DocumentUploadZone,
  ChatBubble,
  type Citation,
  useChatStream,
} from "@rag-platform/shared-ui";
import { API_BASE_URL, api, getAccessToken } from "@/lib/api";
import type { ChatSession, UiMessage } from "@/lib/types";

function newLocalId() {
  return `local-${Math.random().toString(36).slice(2)}`;
}

export default function ComparePage() {
  const router = useRouter();
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [requirements, setRequirements] = useState<Record<string, unknown> | null>(
    null,
  );
  const { stream, streaming } = useChatStream(API_BASE_URL, getAccessToken);

  async function runCompare(files: File[]) {
    const file = files[0];
    if (!file) return;
    setError(null);
    setMessages([]);
    setRequirements(null);
    setStatus("Parsing document…");

    try {
      const form = new FormData();
      form.append("file", file);
      const parsed = await api.upload<{
        filename: string;
        text_preview: string;
      }>("/api/v1/ingest/transient-parse", form);

      setStatus("Extracting requirements…");
      const extracted = await api.post<{ requirements: Record<string, unknown> }>(
        "/api/v1/orchestrate/extract-requirements",
        { text: parsed.text_preview, filename: parsed.filename },
      );
      setRequirements(extracted.requirements);

      setStatus("Comparing against your knowledge base…");
      const session = await api.post<ChatSession>("/api/v1/chat/sessions", {
        title: `Compare: ${parsed.filename}`,
      });

      const query = [
        `Feasibility / comparison for tender "${parsed.filename}".`,
        `Structured requirements: ${JSON.stringify(extracted.requirements)}`,
        "Does equivalent or related work already exist? Cite matching projects or people.",
      ].join("\n\n");

      const userMsg: UiMessage = {
        id: newLocalId(),
        role: "user",
        content: query,
      };
      const assistantId = newLocalId();
      setMessages([
        userMsg,
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);

      const final = await stream(
        `/api/v1/chat/sessions/${session.id}/stream`,
        { content: query },
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + token, streaming: true }
                  : m,
              ),
            );
          },
        },
      );

      const answer = String(final?.answer || "");
      const citations = (final?.citations as Citation[]) || [];
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                id: String(final?.assistant_message_id || assistantId),
                role: "assistant",
                content: answer || m.content,
                citations,
                streaming: false,
                insufficient:
                  !citations.length &&
                  /enough relevant information|insufficient/i.test(answer),
              }
            : m,
        ),
      );
      setStatus(null);
    } catch (err) {
      setStatus(null);
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Compare failed");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6">
      <header>
        <h2 className="text-2xl font-semibold">Compare a tender</h2>
        <p className="mt-1 text-sm text-mute">
          Upload a tender/RFP/spec. We extract requirements, then search your
          knowledge base for related past work.
        </p>
      </header>

      <DocumentUploadZone
        multiple={false}
        onFiles={(files) => void runCompare(files)}
        disabled={streaming || Boolean(status)}
      />

      {status && (
        <p className="text-sm text-accent animate-pulse">{status}</p>
      )}
      {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}

      {requirements && (
        <div className="rounded-[14px] border border-line bg-elevated/70 p-4">
          <p className="text-xs uppercase tracking-wide text-mute">Extracted requirements</p>
          <pre className="mt-2 overflow-x-auto font-mono text-xs text-ink">
            {JSON.stringify(requirements, null, 2)}
          </pre>
        </div>
      )}

      <div className="space-y-4">
        {messages.map((m) => (
          <ChatBubble
            key={m.id}
            role={m.role}
            content={m.content}
            citations={m.citations}
            insufficient={m.insufficient}
            streaming={m.streaming}
          />
        ))}
      </div>

      {messages.length > 0 && !streaming && (
        <Button variant="secondary" onClick={() => router.push("/history")}>
          View in history
        </Button>
      )}
    </div>
  );
}
