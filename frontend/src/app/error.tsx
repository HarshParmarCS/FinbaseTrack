"use client";

import { useEffect } from "react";
import { ErrorFallback } from "@/components/shared/error-fallback";

// Catches rendering errors on pages outside the app shell (sign-in, register, diagnostics).
export default function RootError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return <ErrorFallback onRetry={retry} fullPage />;
}
