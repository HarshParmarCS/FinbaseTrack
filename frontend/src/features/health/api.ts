import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Envelope, HealthOut } from "@/types/api";

export async function getHealth(signal?: AbortSignal): Promise<HealthOut> {
  const body = await api.get<Envelope<HealthOut>>(endpoints.health, { signal });
  return body.data;
}
