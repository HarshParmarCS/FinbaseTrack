"use client";

import { CircleCheck, Info, Loader2, OctagonX, TriangleAlert } from "lucide-react";
import { Toaster as Sonner } from "sonner";

/**
 * App-wide toast host (sonner). The app is light-only, so the theme is fixed instead of reading
 * the system preference. Toasts confirm successful changes; failures stay next to the control
 * that caused them, where the user is looking.
 */
export function Toaster() {
  return (
    <Sonner
      theme="light"
      position="bottom-right"
      closeButton
      icons={{
        success: <CircleCheck className="size-4 text-emerald-600" aria-hidden />,
        info: <Info className="size-4" aria-hidden />,
        warning: <TriangleAlert className="size-4 text-amber-600" aria-hidden />,
        error: <OctagonX className="size-4 text-destructive" aria-hidden />,
        loading: <Loader2 className="size-4 animate-spin" aria-hidden />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
    />
  );
}
