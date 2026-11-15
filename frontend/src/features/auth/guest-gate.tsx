"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { FullPageLoading } from "@/components/shared/full-page-status";
import { useAuth } from "@/features/auth/auth-provider";
import { safeNextPath } from "@/features/auth/redirect";

/** Sign-in and register pages: a user who is already signed in (or just became one) moves on. */
export function GuestGate({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(safeNextPath(next));
    }
  }, [status, router]);

  if (status === "authenticated") return <FullPageLoading label="Signing you in…" />;
  return <>{children}</>;
}
