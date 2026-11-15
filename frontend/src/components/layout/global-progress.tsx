"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";

/**
 * A thin bar under the top bar while any request is in flight. It is decoration (aria-hidden):
 * every section announces its own loading state.
 */
export function GlobalProgress() {
  const busy = useIsFetching() + useIsMutating() > 0;
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden"
    >
      <div
        data-busy={busy}
        className="h-full w-1/3 bg-primary opacity-0 transition-opacity duration-300 data-[busy=true]:animate-[progress_1.2s_ease-in-out_infinite] data-[busy=true]:opacity-100"
      />
    </div>
  );
}
