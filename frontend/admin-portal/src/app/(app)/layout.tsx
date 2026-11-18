"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, cn } from "@rag-platform/shared-ui";
import { api, clearSession, getTenantId, isAuthenticated } from "@/lib/api";

const ORG_ADMIN_NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/config/rules", label: "Rules" },
  { href: "/config/guardrails", label: "Guardrails" },
  { href: "/users", label: "Users" },
  { href: "/profile", label: "Profile" },
];

const SUPER_ADMIN_NAV = [
  { href: "/organizations", label: "Organizations" },
  { href: "/profile", label: "Profile" },
];

export default function AppShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setTenantId(getTenantId());
    api
      .get<{ role: string }>("/api/v1/auth/me")
      .then((me) => {
        setRole(me.role);
        setReady(true);
        if (me.role === "super_admin" && pathname.startsWith("/documents")) {
          router.replace("/organizations");
        }
      })
      .catch(() => {
        clearSession();
        router.replace("/login");
      });
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center text-mute">
        Loading…
      </div>
    );
  }

  const nav = role === "super_admin" ? SUPER_ADMIN_NAV : ORG_ADMIN_NAV;
  const title = role === "super_admin" ? "Super Admin" : "Admin";

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-elevated/80 lg:border-b-0 lg:border-r">
        <div className="px-5 py-6">
          <p className="text-xs uppercase tracking-[0.18em] text-accent">RAG HRMS</p>
          <h1 className="mt-1 text-lg font-semibold">{title}</h1>
          <p className="mt-2 truncate font-mono text-[11px] text-mute" title={tenantId || ""}>
            {role === "super_admin" ? "Platform" : tenantId || "—"}
          </p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col">
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-[10px] px-3 py-2 text-sm whitespace-nowrap",
                  active
                    ? "bg-[var(--rp-accent-soft)] text-accent"
                    : "text-mute hover:bg-[var(--rp-bg-muted)] hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="hidden px-3 pb-6 lg:block">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
          >
            Sign out
          </Button>
        </div>
      </aside>
      <main className="px-4 py-6 sm:px-8 sm:py-8">{children}</main>
    </div>
  );
}
