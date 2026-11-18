"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";

type Org = {
  id: string;
  name: string;
  domain: string;
  is_active: boolean;
  created_at: string;
};

type OrgUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export default function OrganizationDetailPage() {
  const params = useParams();
  const orgId = String(params.orgId || "");

  const [org, setOrg] = useState<Org | null>(null);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("end_user");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError(null);
    try {
      const [orgData, userData] = await Promise.all([
        api.get<Org>(`/api/v1/organizations/${orgId}`),
        api.get<OrgUser[]>(`/api/v1/organizations/${orgId}/users`),
      ]);
      setOrg(orgData);
      setUsers(userData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load organization");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post(`/api/v1/organizations/${orgId}/users`, {
        name,
        email,
        password,
        role,
      });
      setName("");
      setEmail("");
      setPassword("");
      setRole("end_user");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(user: OrgUser) {
    setError(null);
    try {
      const action = user.is_active ? "disable" : "enable";
      await api.post(`/api/v1/organizations/${orgId}/users/${user.id}/${action}`, {});
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed");
    }
  }

  async function resetPassword(userId: string) {
    const next = window.prompt("New password (min 8 characters)");
    if (!next) return;
    setError(null);
    try {
      await api.post(`/api/v1/organizations/${orgId}/users/${userId}/reset-password`, {
        new_password: next,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed");
    }
  }

  if (loading && !org) {
    return <p className="text-mute">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <Link href="/organizations" className="text-sm text-accent hover:underline">
          ← Back to organizations
        </Link>
        <h2 className="mt-3 text-2xl font-semibold">{org?.name || "Organization"}</h2>
        <p className="mt-1 text-sm text-mute">
          {org?.is_active ? "Active" : "Disabled"} ·{" "}
          <span className="font-mono text-[11px]">{orgId}</span>
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
        <h3 className="text-lg font-medium">Add user or admin</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-mute">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Password</span>
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-mute">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2"
            >
              <option value="end_user">User</option>
              <option value="admin">Organization Admin</option>
            </select>
          </label>
        </div>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Add to organization"}
        </Button>
      </form>

      <div className="overflow-x-auto rounded-[14px] border border-line">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-elevated/80 text-mute">
            <tr>
              <th className="px-4 py-3 font-medium">User</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-mute">
                  No users in this organization.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.full_name || "—"}</div>
                    <div className="text-mute">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    {u.role === "admin" ? "Organization Admin" : "User"}
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? (
                      <span className="text-accent">Active</span>
                    ) : (
                      <span className="text-[var(--rp-danger)]">Disabled</span>
                    )}
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => void toggleActive(u)}
                    >
                      {u.is_active ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => void resetPassword(u.id)}
                    >
                      Reset password
                    </Button>
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
