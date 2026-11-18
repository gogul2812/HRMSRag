"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  Button,
  DocumentUploadZone,
  StatusBadge,
  formatDate,
} from "@rag-platform/shared-ui";
import { API_BASE_URL, api, getAccessToken } from "@/lib/api";
import type { DocumentRow } from "@/lib/types";

const DOC_TYPES = ["project", "employee", "policy", "other"] as const;

type DocContent = {
  id: string;
  filename: string;
  content_type: string | null;
  text: string | null;
  is_text: boolean;
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [docType, setDocType] = useState<(typeof DOC_TYPES)[number]>("project");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [viewing, setViewing] = useState<DocContent | null>(null);
  const [viewBusy, setViewBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api.get<DocumentRow[]>("/api/v1/ingest/documents");
      setDocs(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load documents");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const busy = docs.some((d) => d.status === "pending" || d.status === "processing");
    if (!busy) return;
    const id = window.setInterval(() => {
      void load();
    }, 2500);
    return () => window.clearInterval(id);
  }, [docs, load]);

  async function uploadFiles(files: File[]) {
    setUploading(true);
    setMessage(null);
    setError(null);
    try {
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        form.append("doc_type", docType);
        await api.upload<{ document: DocumentRow; message: string }>(
          "/api/v1/ingest/upload",
          form,
        );
      }
      setMessage(`Uploaded ${files.length} file(s). Status updates live below.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function removeDoc(id: string) {
    try {
      await api.delete(`/api/v1/ingest/documents/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function viewDoc(id: string) {
    setViewBusy(true);
    setError(null);
    try {
      const content = await api.get<DocContent>(`/api/v1/ingest/documents/${id}/content`);
      setViewing(content);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open document");
    } finally {
      setViewBusy(false);
    }
  }

  async function downloadDoc(id: string, filename: string) {
    setError(null);
    try {
      const token = getAccessToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/ingest/documents/${id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        throw new Error(`Download failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold">Documents</h2>
        <p className="mt-1 text-sm text-mute">
          Upload knowledge-base files, view content, and watch ingestion status update live.
        </p>
      </header>

      <section className="space-y-4 rounded-[14px] border border-line bg-elevated/70 p-5">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-mute">Document type</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as (typeof DOC_TYPES)[number])}
              className="mt-1 block rounded-[10px] border border-line bg-canvas px-3 py-2"
            >
              {DOC_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <Button variant="secondary" onClick={() => void load()} disabled={uploading}>
            Refresh
          </Button>
        </div>
        <DocumentUploadZone onFiles={(files) => void uploadFiles(files)} disabled={uploading} />
        {message && <p className="text-sm text-accent">{message}</p>}
        {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}
      </section>

      <section className="overflow-hidden rounded-[14px] border border-line bg-elevated/70">
        <div className="border-b border-line px-5 py-3 text-sm text-mute">
          {docs.length} document{docs.length === 1 ? "" : "s"}
        </div>
        <ul className="divide-y divide-line">
          {docs.length === 0 && (
            <li className="px-5 py-8 text-sm text-mute">No documents yet.</li>
          )}
          {docs.map((doc) => (
            <li
              key={doc.id}
              className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{doc.filename}</p>
                <p className="mt-1 font-mono text-xs text-mute">
                  {doc.doc_type} · {formatDate(doc.updated_at)}
                  {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ""}
                </p>
                {doc.error_message && (
                  <p className="mt-1 text-xs text-[var(--rp-danger)]">{doc.error_message}</p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={doc.status} />
                <Button
                  variant="secondary"
                  disabled={viewBusy}
                  onClick={() => void viewDoc(doc.id)}
                >
                  View
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => void downloadDoc(doc.id, doc.filename)}
                >
                  Download
                </Button>
                <Button variant="ghost" onClick={() => void removeDoc(doc.id)}>
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-[14px] border border-line bg-canvas shadow-xl">
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
              <div className="min-w-0">
                <p className="truncate font-medium">{viewing.filename}</p>
                <p className="text-xs text-mute">{viewing.content_type || "unknown type"}</p>
              </div>
              <Button variant="ghost" onClick={() => setViewing(null)}>
                Close
              </Button>
            </div>
            <div className="overflow-auto px-5 py-4">
              {viewing.is_text && viewing.text != null ? (
                <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                  {viewing.text}
                </pre>
              ) : (
                <div className="space-y-3 text-sm text-mute">
                  <p>This file is not plain text — use Download to open it locally.</p>
                  <Button
                    onClick={() => void downloadDoc(viewing.id, viewing.filename)}
                  >
                    Download file
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
