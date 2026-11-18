"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api, setSession } from "@/lib/api";

type Org = { id: string; name: string };

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [platformAdmin, setPlatformAdmin] = useState(false);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get<Org[]>("/api/v1/organizations/public")
      .then(setOrgs)
      .catch(() => setOrgs([]));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body: Record<string, string> = { email, password };
      if (!platformAdmin) {
        if (!organizationId) {
          setError("Select an organization");
          setLoading(false);
          return;
        }
        body.organization_id = organizationId;
      }
      const tokens = await api.post<{
        access_token: string;
        refresh_token: string;
        token_type: string;
        expires_in: number;
      }>("/api/v1/auth/login", body);
      setSession({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        tenant_id: organizationId || "",
      });

      const me = await api.get<{ role: string }>("/api/v1/auth/me");
      if (me.role === "super_admin") {
        router.replace("/organizations");
      } else {
        router.replace("/documents");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center px-4">
      <div className="w-full max-w-md rounded-[14px] border border-line bg-elevated/90 p-8 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-accent">RAG HRMS</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Admin Portal</h1>
        <p className="mt-2 text-sm text-mute">
          Sign in as Super Admin or Organization Admin.
        </p>

        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="flex items-center gap-2 text-sm text-mute">
            <input
              type="checkbox"
              checked={platformAdmin}
              onChange={(e) => setPlatformAdmin(e.target.checked)}
            />
            Platform Super Admin (no organization)
          </label>

          {!platformAdmin && (
            <label className="block text-sm">
              <span className="text-mute">Organization</span>
              <select
                required={!platformAdmin}
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
              >
                <option value="">Select organization…</option>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="block text-sm">
            <span className="text-mute">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Password</span>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
            />
          </label>

          {error && (
            <p className="rounded-[10px] border border-[var(--rp-danger)]/40 bg-[var(--rp-danger)]/10 px-3 py-2 text-sm text-[var(--rp-danger)]">
              {error}
            </p>
          )}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </main>
  );
}
