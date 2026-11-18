"use client";

import { useEffect, useState } from "react";
import { ApiError, Button } from "@rag-platform/shared-ui";
import { api } from "@/lib/api";

type Profile = {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  job_title: string | null;
  department: string | null;
  location: string | null;
  role: string;
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get<Profile>("/api/v1/auth/me")
      .then((me) => {
        setProfile(me);
        setName(me.full_name || "");
        setPhone(me.phone || "");
        setJobTitle(me.job_title || "");
        setDepartment(me.department || "");
        setLocation(me.location || "");
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load profile");
      });
  }, []);

  async function saveProfile() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.patch<Profile>("/api/v1/auth/me", {
        name: name.trim() || null,
        phone: phone.trim() || null,
        job_title: jobTitle.trim() || null,
        department: department.trim() || null,
        location: location.trim() || null,
      });
      setProfile(updated);
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save profile");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword() {
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.post("/api/v1/auth/me/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Password changed.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setBusy(false);
    }
  }

  if (!profile && !error) {
    return <p className="text-mute">Loading profile…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold">Profile</h2>
        <p className="mt-1 text-sm text-mute">
          Personal and professional details, plus change password.
        </p>
      </header>

      {message && <p className="text-sm text-accent">{message}</p>}
      {error && <p className="text-sm text-[var(--rp-danger)]">{error}</p>}

      <section className="space-y-4 rounded-[14px] border border-line bg-elevated/70 p-5">
        <h3 className="font-medium">Account</h3>
        <p className="text-sm text-mute">
          {profile?.email} · {profile?.role?.replace("_", " ")}
        </p>

        <h3 className="pt-2 font-medium">Personal details</h3>
        <label className="block text-sm">
          <span className="text-mute">Full name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Phone</span>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Location</span>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
            placeholder="City / office"
          />
        </label>

        <h3 className="pt-2 font-medium">Professional details</h3>
        <label className="block text-sm">
          <span className="text-mute">Job title</span>
          <input
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Department</span>
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>

        <Button onClick={() => void saveProfile()} disabled={busy}>
          Save profile
        </Button>
      </section>

      <section className="space-y-4 rounded-[14px] border border-line bg-elevated/70 p-5">
        <h3 className="font-medium">Change password</h3>
        <label className="block text-sm">
          <span className="text-mute">Current password</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">New password</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-mute">Confirm new password</span>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 w-full rounded-[10px] border border-line bg-canvas px-3 py-2 outline-none focus:border-accent"
          />
        </label>
        <Button
          onClick={() => void changePassword()}
          disabled={busy || !currentPassword || !newPassword}
        >
          Change password
        </Button>
      </section>
    </div>
  );
}
