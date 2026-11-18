"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";

type OrgUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export default function UsersPage() {
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("end_user");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<OrgUser[]>("/api/v1/organizations/me/users");
      setUsers(data);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to load users (Organization Admin only)",
      );
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
      await api.post("/api/v1/organizations/me/users", {
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

  async function removeUser(id: string) {
    setError(null);
    try {
      await api.delete(`/api/v1/organizations/me/users/${id}`);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function resetPassword(id: string) {
    const next = window.prompt("New password (min 8 characters)");
    if (!next) return;
    setError(null);
    try {
      await api.post(`/api/v1/organizations/me/users/${id}/reset-password`, {
        new_password: next,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed");
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h2 className="text-2xl font-semibold">Users</h2>
        <p className="mt-1 text-sm text-mute">
          Manage users in your organization only. Organization is taken from your
          login — you cannot switch it.
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
        <h3 className="text-lg font-medium">Create user</h3>
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
          {saving ? "Saving…" : "Create user"}
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
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-mute">
                  Loading…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-mute">
                  No users yet.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.full_name || "—"}</div>
                    <div className="text-mute">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">{u.role}</td>
                  <td className="px-4 py-3">
                    {u.is_active ? "Active" : "Disabled"}
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => void resetPassword(u.id)}
                    >
                      Reset password
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => void removeUser(u.id)}
                    >
                      Delete
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
