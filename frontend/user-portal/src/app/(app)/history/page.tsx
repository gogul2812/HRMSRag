"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, Button, formatDate } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";
import type { ChatSession } from "@/lib/types";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await api.get<ChatSession[]>("/api/v1/chat/sessions");
      setSessions(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load history");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(id: string) {
    try {
      await api.delete(`/api/v1/chat/sessions/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">History</h2>
          <p className="mt-1 text-sm text-mute">Past conversations for this account.</p>
        </div>
        <Button variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </header>

      {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}

      <ul className="overflow-hidden rounded-[14px] border border-line bg-elevated/70 divide-y divide-line">
        {sessions.length === 0 && (
          <li className="px-5 py-10 text-center text-sm text-mute">No conversations yet.</li>
        )}
        {sessions.map((s) => (
          <li
            key={s.id}
            className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <Link
                href={`/chat/${s.id}`}
                className="font-medium text-ink hover:text-accent"
              >
                {s.title || "Untitled chat"}
              </Link>
              <p className="mt-1 text-xs text-mute">{formatDate(s.updated_at)}</p>
            </div>
            <div className="flex gap-2">
              <Link href={`/chat/${s.id}`}>
                <Button variant="secondary">Open</Button>
              </Link>
              <Button variant="ghost" onClick={() => void remove(s.id)}>
                Delete
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
