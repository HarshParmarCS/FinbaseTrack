import { z } from "zod";

/**
 * The only place that reads environment variables.
 * Public values are inlined into the browser bundle and must never hold secrets.
 * Server-only settings live in server-env.ts so they never reach the browser bundle.
 */
const publicSchema = z.object({
  NEXT_PUBLIC_APP_NAME: z.string().min(1),
  // Empty means "same origin": the browser calls /api/v1 on the Next.js origin and the rewrite in
  // next.config.ts forwards it. A full URL (for example http://localhost:8000) calls the backend
  // directly, which requires CORS and the origin to be listed in the backend's ALLOWED_ORIGINS.
  NEXT_PUBLIC_API_BASE_URL: z
    .union([z.literal(""), z.url({ protocol: /^https?$/ })])
    .refine((value) => !value.endsWith("/"), "must not end with a slash"),
});

export function parsePublicEnv(source: Record<string, string | undefined>) {
  return publicSchema.parse({
    NEXT_PUBLIC_APP_NAME: source.NEXT_PUBLIC_APP_NAME ?? "FinTasks",
    NEXT_PUBLIC_API_BASE_URL: source.NEXT_PUBLIC_API_BASE_URL ?? "",
  });
}

// Next.js only inlines NEXT_PUBLIC_* values when they are read as literal `process.env.NAME`.
export const publicEnv = parsePublicEnv({
  NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
});
