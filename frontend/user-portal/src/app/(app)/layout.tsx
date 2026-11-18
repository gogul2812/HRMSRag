"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, cn } from "@rag-platform/shared-ui";
import { clearSession, isAuthenticated } from "@/lib/api";

const NAV = [
  { href: "/chat", label: "Chat" },
  { href: "/compare", label: "Compare" },
  { href: "/history", label: "History" },
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

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="shrink-0 border-b border-line bg-elevated/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-accent">RAG HRMS</p>
              <p className="text-sm font-semibold">Knowledge Assistant</p>
            </div>
            <nav className="flex gap-1">
              {NAV.map((item) => {
                const active =
                  pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-[10px] px-3 py-1.5 text-sm",
                      active
                        ? "bg-[var(--rp-accent-soft)] text-accent"
                        : "text-mute hover:text-ink hover:bg-[var(--rp-bg-muted)]",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <Button
            variant="ghost"
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
