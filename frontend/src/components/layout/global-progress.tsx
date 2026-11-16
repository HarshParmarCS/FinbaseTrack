"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";

/**
 * The faded violet glow line under the top bar (from the Finbase header). While any request is
 * in flight a brighter segment runs along it. Decoration only (aria-hidden): every section
 * announces its own loading state.
 */
export function GlobalProgress() {
  const busy = useIsFetching() + useIsMutating() > 0;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-px">
      <div className="absolute inset-0 bg-glow-line opacity-60" />
      <div className="absolute inset-0 overflow-hidden">
        <div
          data-busy={busy}
          className="h-0.5 w-1/3 -translate-y-px bg-brand-500 opacity-0 transition-opacity duration-300 data-[busy=true]:animate-[progress_1.2s_ease-in-out_infinite] data-[busy=true]:opacity-100"
        />
      </div>
    </div>
  );
}
