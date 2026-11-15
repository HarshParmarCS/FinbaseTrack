export const DEFAULT_AFTER_LOGIN = "/dashboard";

export type SessionEnd = "expired" | "signed-out" | null;

/**
 * Accept only same-site paths for the `next` parameter, so a crafted link cannot send a user to
 * another site after sign-in (open redirect). Anything else falls back to the dashboard.
 */
export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return DEFAULT_AFTER_LOGIN;
  if (value.includes("\\") || /[\u0000-\u001f]/.test(value)) return DEFAULT_AFTER_LOGIN;
  if (/^\/(login|register)(?:[/?#]|$)/.test(value)) return DEFAULT_AFTER_LOGIN;
  return value;
}

/** Where an unauthenticated user is sent. `next` is dropped after a deliberate sign-out. */
export function buildLoginUrl(end: SessionEnd, currentPath: string): string {
  const params = new URLSearchParams();
  if (end === "expired") params.set("reason", "expired");
  if (end !== "signed-out") params.set("next", safeNextPath(currentPath));
  const query = params.toString();
  return query ? `/login?${query}` : "/login";
}
