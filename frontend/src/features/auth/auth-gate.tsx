"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { FullPageError, FullPageLoading } from "@/components/shared/full-page-status";
import { useAuth } from "@/features/auth/auth-provider";
import { buildLoginUrl } from "@/features/auth/redirect";

/**
 * Convenience for the UI, not a security boundary: it only decides what to show. The backend
 * rejects every API call without a valid session no matter what this component renders.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { status, endedBy, retry } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(buildLoginUrl(endedBy, `${pathname}${window.location.search}`));
    }
  }, [status, endedBy, pathname, router]);

  if (status === "authenticated") return <>{children}</>;
  if (status === "error") {
    return (
      <FullPageError
        title="Cannot check your session"
        description="The server could not be reached. Check that the backend is running, then try again."
        onRetry={retry}
      />
    );
  }
  return <FullPageLoading label={status === "loading" ? "Loading…" : "Redirecting to sign in…"} />;
}
