"use client";

import { useCallback, useRef, useState } from "react";

export type StreamHandlers = {
  onToken?: (token: string) => void;
  onStatus?: (status: string) => void;
  onFinal?: (payload: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
};

/**
 * Shared SSE client for chat streaming (User Portal + Admin preview).
 * Expects events: `status` ({status}), `token` ({token}), `final` (JSON object).
 */
export function useChatStream(baseUrl: string, getToken: () => string | null) {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const stream = useCallback(
    async (
      path: string,
      body: unknown,
      handlers: StreamHandlers = {},
    ): Promise<Record<string, unknown> | null> => {
      cancel();
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);

      let finalPayload: Record<string, unknown> | null = null;

      try {
        const token = getToken();
        const res = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            Accept: "text/event-stream",
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          const text = await res.text();
          throw new Error(text || `Stream failed (${res.status})`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let eventName = "message";
        let dataLines: string[] = [];

        const flush = () => {
          if (!dataLines.length) return;
          const raw = dataLines.join("\n");
          dataLines = [];
          let parsed: unknown = raw;
          try {
            parsed = JSON.parse(raw);
          } catch {
            /* keep string */
          }
          if (eventName === "token") {
            const tokenText =
              typeof parsed === "object" &&
              parsed &&
              "token" in parsed
                ? String((parsed as { token: unknown }).token)
                : String(parsed);
            handlers.onToken?.(tokenText);
          } else if (eventName === "status") {
            const statusText =
              typeof parsed === "object" && parsed && "status" in parsed
                ? String((parsed as { status: unknown }).status)
                : String(parsed);
            handlers.onStatus?.(statusText);
          } else if (eventName === "final") {
            finalPayload =
              typeof parsed === "object" && parsed
                ? (parsed as Record<string, unknown>)
                : { answer: String(parsed) };
            handlers.onFinal?.(finalPayload);
          }
          eventName = "message";
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split(/\r?\n/);
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).replace(/^\s/, ""));
            } else if (line === "") {
              flush();
            }
          }
        }
        flush();
        return finalPayload;
      } catch (err) {
        if ((err as Error).name === "AbortError") return finalPayload;
        const error = err instanceof Error ? err : new Error(String(err));
        handlers.onError?.(error);
        throw error;
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [baseUrl, cancel, getToken],
  );

  return { stream, streaming, cancel };
}
