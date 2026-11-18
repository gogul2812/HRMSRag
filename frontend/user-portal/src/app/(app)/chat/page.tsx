"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  ApiError,
  Button,
  ChatBubble,
  type Citation,
  useChatStream,
} from "@rag-platform/shared-ui";
import { API_BASE_URL, api, getAccessToken } from "@/lib/api";
import type { ChatSession, ChatSessionDetail, UiMessage } from "@/lib/types";

function newLocalId() {
  return `local-${Math.random().toString(36).slice(2)}`;
}

export default function ChatPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [comparingNote, setComparingNote] = useState<string | null>(null);
  const [mobileSessionsOpen, setMobileSessionsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { stream, streaming } = useChatStream(API_BASE_URL, getAccessToken);

  const loadSessions = useCallback(async () => {
    try {
      const rows = await api.get<ChatSession[]>("/api/v1/chat/sessions");
      setSessions(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load sessions");
    }
  }, []);

  const loadSession = useCallback(async (id: string) => {
    try {
      const detail = await api.get<ChatSessionDetail>(`/api/v1/chat/sessions/${id}`);
      setSessionId(id);
      setMessages(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role === "assistant" ? "assistant" : "user",
          content: m.content,
          citations: m.citations as Citation[],
        })),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load chat");
    }
  }, []);

  useEffect(() => {
    void loadSessions();
    const resume = sessionStorage.getItem("rag_resume_session");
    if (resume) {
      sessionStorage.removeItem("rag_resume_session");
      void loadSession(resume);
    }
  }, [loadSessions, loadSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, comparingNote]);

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const created = await api.post<ChatSession>("/api/v1/chat/sessions", {
      title: null,
    });
    setSessionId(created.id);
    await loadSessions();
    return created.id;
  }

  async function sendText(content: string) {
    const text = content.trim();
    if (!text || streaming) return;
    setError(null);
    setInput("");

    const sid = await ensureSession();
    const userMsg: UiMessage = { id: newLocalId(), role: "user", content: text };
    const assistantId = newLocalId();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);

    try {
      const final = await stream(
        `/api/v1/chat/sessions/${sid}/stream`,
        { content: text },
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

      const citations = (final?.citations as Citation[]) || [];
      const answer = String(final?.answer || "");
      const assistantMessageId = final?.assistant_message_id
        ? String(final.assistant_message_id)
        : assistantId;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                id: assistantMessageId,
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
      await loadSessions();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Stream failed";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content:
                  "I couldn't generate a response for that — the assistant is temporarily unavailable. Please try again.",
                streaming: false,
                isError: true,
              }
            : m,
        ),
      );
      setError(message);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await sendText(input);
  }

  async function onFeedback(messageId: string, rating: "up" | "down") {
    try {
      await api.post(`/api/v1/chat/messages/${messageId}/feedback`, { rating });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Feedback failed");
    }
  }

  async function onAttach(file: File) {
    setComparingNote("Comparing against your knowledge base…");
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const parsed = await api.upload<{
        filename: string;
        text_preview: string;
        chunk_count: number;
      }>("/api/v1/ingest/transient-parse", form);

      const extracted = await api.post<{
        requirements: Record<string, unknown>;
      }>("/api/v1/orchestrate/extract-requirements", {
        text: parsed.text_preview,
        filename: parsed.filename,
      });

      const reqs = extracted.requirements || {};
      const query = [
        `Does related work already exist for this tender/spec (${parsed.filename})?`,
        `Extracted requirements: ${JSON.stringify(reqs)}`,
        "Compare against past projects and available people. Cite sources.",
      ].join("\n\n");

      setComparingNote(null);
      await sendText(query);
    } catch (err) {
      setComparingNote(null);
      setError(err instanceof ApiError ? err.message : "Attachment flow failed");
    }
  }

  const currentTitle =
    sessions.find((s) => s.id === sessionId)?.title || (sessionId ? "Untitled chat" : "New chat");

  const sessionsList = (onPick?: () => void) => (
    <>
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-3">
        <p className="text-xs uppercase tracking-wide text-mute">Sessions</p>
        <Button
          variant="secondary"
          className="!px-2 !py-1 text-xs"
          onClick={async () => {
            setSessionId(null);
            setMessages([]);
            const created = await api.post<ChatSession>("/api/v1/chat/sessions", {});
            setSessionId(created.id);
            await loadSessions();
            onPick?.();
          }}
        >
          New
        </Button>
      </div>
      <ul className="flex-1 overflow-y-auto p-2">
        {sessions.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => {
                void loadSession(s.id);
                onPick?.();
              }}
              className={`mb-1 w-full truncate rounded-[10px] px-3 py-2 text-left text-sm ${
                sessionId === s.id
                  ? "bg-[var(--rp-accent-soft)] text-accent"
                  : "text-mute hover:bg-[var(--rp-bg-muted)] hover:text-ink"
              }`}
            >
              {s.title || "Untitled chat"}
            </button>
          </li>
        ))}
        {sessions.length === 0 && (
          <li className="px-3 py-6 text-xs text-mute">No chats yet.</li>
        )}
      </ul>
    </>
  );

  return (
    <div className="mx-auto grid h-full max-w-6xl grid-cols-1 grid-rows-[auto_1fr] md:grid-cols-[220px_1fr] md:grid-rows-1">
      <aside className="hidden min-h-0 border-r border-line bg-elevated/40 md:flex md:flex-col">
        {sessionsList()}
      </aside>

      <button
        type="button"
        onClick={() => setMobileSessionsOpen(true)}
        className="flex items-center gap-2 border-b border-line px-4 py-3 text-left text-sm text-mute md:hidden"
      >
        <span aria-hidden="true">☰</span>
        <span className="truncate">{currentTitle}</span>
      </button>

      <AnimatePresence>
        {mobileSessionsOpen && (
          <motion.div
            className="fixed inset-0 z-40 flex md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="absolute inset-0 bg-black/60"
              onClick={() => setMobileSessionsOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
            <motion.div
              className="relative flex h-full w-[min(80vw,300px)] flex-col bg-elevated"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              {sessionsList(() => setMobileSessionsOpen(false))}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <section className="flex min-h-0 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 && !comparingNote && (
            <div className="mx-auto max-w-lg pt-16 text-center">
              <h2 className="text-2xl font-semibold">Ask anything from your corpus</h2>
              <p className="mt-2 text-sm text-mute">
                Answers stream live with source citations. Attach a tender to compare.
              </p>
            </div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <ChatBubble
                key={m.id}
                role={m.role}
                content={m.content}
                citations={m.citations}
                insufficient={m.insufficient}
                isError={m.isError}
                streaming={m.streaming}
                onFeedback={
                  m.role === "assistant" &&
                  !m.streaming &&
                  !m.isError &&
                  !m.id.startsWith("local-")
                    ? (rating) => void onFeedback(m.id, rating)
                    : undefined
                }
              />
            ))}
          </AnimatePresence>
          {comparingNote && (
            <p className="text-center text-sm text-accent animate-pulse">{comparingNote}</p>
          )}
          <div ref={bottomRef} />
        </div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className="mx-4 mb-2 flex items-start justify-between gap-3 rounded-[10px] border border-[var(--rp-danger)]/40 bg-[var(--rp-danger)]/10 px-3 py-2 text-sm text-[var(--rp-danger)] sm:mx-6"
            >
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="shrink-0 text-[var(--rp-danger)]/70 hover:text-[var(--rp-danger)]"
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <form
          onSubmit={onSubmit}
          className="border-t border-line bg-elevated/60 px-4 py-4 sm:px-6"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <input
              ref={fileRef}
              type="file"
              className="sr-only"
              accept=".pdf,.md,.docx,.txt,.png,.jpg,.jpeg"
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) void onAttach(f);
              }}
            />
            <Button
              type="button"
              variant="secondary"
              disabled={streaming || Boolean(comparingNote)}
              onClick={() => fileRef.current?.click()}
              title="Attach tender / spec"
            >
              Attach
            </Button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={2}
              placeholder="Ask a question…"
              className="min-h-[44px] flex-1 resize-none rounded-[12px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendText(input);
                }
              }}
            />
            <Button type="submit" disabled={streaming || !input.trim()}>
              Send
            </Button>
          </div>
          <p className="mx-auto mt-2 max-w-3xl text-xs text-mute">
            Or open{" "}
            <button
              type="button"
              className="text-accent underline"
              onClick={() => router.push("/compare")}
            >
              Compare
            </button>{" "}
            for a dedicated tender upload flow.
          </p>
        </form>
      </section>
    </div>
  );
}
