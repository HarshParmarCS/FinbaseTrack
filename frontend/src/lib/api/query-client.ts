import { QueryClient } from "@tanstack/react-query";
import { isApiError } from "@/lib/api/errors";

const MAX_RETRIES = 2;

/**
 * Client errors (4xx) will not change by asking again, so they are never retried.
 * Network failures (status 0) and server errors (5xx) are retried a couple of times.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
  return failureCount < MAX_RETRIES;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: shouldRetry,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
