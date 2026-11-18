"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";

type Org = {
  id: string;
  name: string;
  domain: string;
  is_active: boolean;
  created_at: string;
};

export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Org[]>("/api/v1/organizations");
      setOrgs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load organizations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/v1/organizations", {
        name,
        admin_name: adminName,
        admin_email: adminEmail,
        admin_password: adminPassword,
      });
      setName("");
      setAdminName("");
      setAdminEmail("");
      setAdminPassword("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  async function disableOrg(id: string) {
    setError(null);
    try {
      await api.post(`/api/v1/organizations/${id}/disable`, {});
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Disable failed");
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h2 className="text-2xl font-semibold">Organizations</h2>
        <p className="mt-1 text-sm text-mute">
          Click an organization to view its users, add admins/users, or disable accounts.
        </p>
      </div>

      {error && (
        <p className="rounded-[10px] border border-[var(--rp-danger)]/40 bg-[var(--rp-danger)]/10 px-3 py-2 text-sm text-[var(--rp-danger)]">
          {error}
        </p>
      )}

      <form
        onSubmit={onCreate}
        className="space-y-3 rounded-[14px] border border-line bg-elevated/60 p-5"
      >
        <h3 className="text-lg font-medium">Create organization</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="text-mute">Organization name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Admin name</span>
            <input
              required
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Admin email</span>
            <input
              required
              type="email"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="text-mute">Admin password</span>
            <input
              required
              type="password"
              minLength={8}
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
        </div>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </form>

      <div className="overflow-x-auto rounded-[14px] border border-line">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-elevated/80 text-mute">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-mute">
                  Loading…
                </td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-mute">
                  No organizations yet.
                </td>
              </tr>
            ) : (
              orgs.map((o) => (
                <tr key={o.id} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <Link
                      href={`/organizations/${o.id}`}
                      className="font-medium text-accent hover:underline"
                    >
                      {o.name}
                    </Link>
                    <div className="font-mono text-[11px] text-mute">{o.id}</div>
                  </td>
                  <td className="px-4 py-3">
                    {o.is_active ? (
                      <span className="text-accent">Active</span>
                    ) : (
                      <span className="text-[var(--rp-danger)]">Disabled</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-mute">
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <Link
                      href={`/organizations/${o.id}`}
                      className="text-sm text-accent hover:underline"
                    >
                      View users
                    </Link>
                    {o.is_active && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => void disableOrg(o.id)}
                      >
                        Disable org
                      </Button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
