"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

/** Resume a conversation — redirects into /chat which loads the session. */
export default function ChatByIdPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    if (params.id) {
      sessionStorage.setItem("rag_resume_session", params.id);
      router.replace("/chat");
    }
  }, [params.id, router]);

  return (
    <div className="grid min-h-[50vh] place-items-center">
      <div className="flex flex-col items-center gap-3 text-mute">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" />
        <p className="text-sm">Opening chat…</p>
      </div>
    </div>
  );
}
