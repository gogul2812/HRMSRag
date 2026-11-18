"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api, setSession } from "@/lib/api";

type Org = { id: string; name: string };

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationId, setOrganizationId] = useState("");
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
      const tokens = await api.post<{
        access_token: string;
        refresh_token: string;
      }>("/api/v1/auth/login", {
        email,
        password,
        organization_id: organizationId,
      });
      setSession({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        tenant_id: organizationId,
      });
      router.replace("/chat");
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
        <h1 className="mt-2 text-3xl font-semibold text-ink">Ask your knowledge base</h1>
        <p className="mt-2 text-sm text-mute">
          Select your organization, then sign in with email and password.
        </p>
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block text-sm">
            <span className="text-mute">Organization</span>
            <select
              required
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
          <p className="text-center text-sm text-mute">
            No account?{" "}
            <Link href="/register" className="text-accent hover:underline">
              Register
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
