"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getMyActivity, getProjectActivity } from "@/features/activity/api";
import { activityKeys } from "@/features/activity/keys";
import type { PageParams } from "@/types/api";

export function useMyActivity(params: PageParams = {}) {
  return useQuery({
    queryKey: activityKeys.mine(params),
    queryFn: ({ signal }) => getMyActivity(params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useProjectActivity(projectId: string, params: PageParams = {}) {
  return useQuery({
    queryKey: activityKeys.project(projectId, params),
    queryFn: ({ signal }) => getProjectActivity(projectId, params, signal),
    placeholderData: keepPreviousData,
  });
}
