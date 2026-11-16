"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import { IconTile } from "@/components/shared/icon-tile";
import { Button, buttonVariants } from "@/components/ui/button";

type Props = { onRetry: () => void; fullPage?: boolean };

/**
 * Shown by the route error boundaries when rendering crashes. It never shows the error itself:
 * details go to the browser console only, as the coding standards require for stack traces.
 */
export function ErrorFallback({ onRetry, fullPage = false }: Props) {
  return (
    <div
      role="alert"
      className={
        fullPage
          ? "flex min-h-svh flex-col items-center justify-center gap-3 px-6 text-center"
          : "flex flex-col items-center justify-center gap-3 rounded-2xl bg-card px-6 py-16 text-center shadow-card"
      }
    >
      <IconTile icon={TriangleAlert} tone="danger" size="lg" />
      <h1 className="text-xl font-bold tracking-tight">Something went wrong</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This page could not be displayed. Try again, or go back to the dashboard.
      </p>
      <div className="flex gap-2">
        <Button onClick={onRetry}>Try again</Button>
        <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
          Dashboard
        </Link>
      </div>
    </div>
  );
}
