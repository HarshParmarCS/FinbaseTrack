"use client";

import { useEffect } from "react";
import { ErrorFallback } from "@/components/shared/error-fallback";

// Catches rendering errors inside the app pages; the sidebar and top bar keep working.
export default function AppError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return <ErrorFallback onRetry={retry} />;
}
