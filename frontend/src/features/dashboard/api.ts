import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { DashboardStats, Envelope } from "@/types/api";

export async function getDashboardStats(signal?: AbortSignal): Promise<DashboardStats> {
  return (await api.get<Envelope<DashboardStats>>(endpoints.dashboard.stats, { signal })).data;
}
