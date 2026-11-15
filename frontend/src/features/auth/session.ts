import type { QueryClient } from "@tanstack/react-query";
import { getCurrentUser } from "@/features/auth/api";
import { authKeys } from "@/features/auth/keys";
import { CSRF_COOKIE, readCookie } from "@/lib/api/client";
import { isUnauthorized } from "@/lib/api/errors";
import type { UserOut } from "@/types/api";

/**
 * The signed-in user, or null when there is no session. The HttpOnly cookies cannot be read from
 * JavaScript, so the readable csrf_token cookie serves as a hint: without it there is no session
 * and no request is needed. With it, the backend decides (and refreshes the session if needed).
 */
export async function fetchSession(signal?: AbortSignal): Promise<UserOut | null> {
  if (!readCookie(CSRF_COOKIE)) return null;
  try {
    return await getCurrentUser(signal);
  } catch (error) {
    if (isUnauthorized(error)) return null;
    throw error;
  }
}

/** Forget everything fetched for the previous user. The session query itself is kept. */
export function resetUserData(queryClient: QueryClient): void {
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== authKeys.all[0] });
}
