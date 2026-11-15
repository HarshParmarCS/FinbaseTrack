import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ActivityOut, PageParams, PagedEnvelope } from "@/types/api";

export function getMyActivity(params: PageParams, signal?: AbortSignal) {
  return api.get<PagedEnvelope<ActivityOut>>(endpoints.dashboard.activity, {
    query: params,
    signal,
  });
}

export function getProjectActivity(projectId: string, params: PageParams, signal?: AbortSignal) {
  return api.get<PagedEnvelope<ActivityOut>>(endpoints.projects.activity(projectId), {
    query: params,
    signal,
  });
}
