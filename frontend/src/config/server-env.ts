import { z } from "zod";

/** Server-only settings. Import this from next.config.ts or server code, never from client code. */
const serverSchema = z.object({
  BACKEND_INTERNAL_URL: z
    .url({ protocol: /^https?$/ })
    .refine((value) => !value.endsWith("/"), "must not end with a slash"),
});

export function parseServerEnv(source: Record<string, string | undefined>) {
  return serverSchema.parse({
    BACKEND_INTERNAL_URL: source.BACKEND_INTERNAL_URL ?? "http://localhost:8000",
  });
}
