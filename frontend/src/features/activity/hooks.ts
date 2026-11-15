"use client";

import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getMyActivity, getProjectActivity } from "@/features/activity/api";
import { activityKeys } from "@/features/activity/keys";
import type { ActivityOut, PageParams, PagedEnvelope } from "@/types/api";

export const ACTIVITY_PAGE_SIZE = 20;

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

function nextPage(last: PagedEnvelope<ActivityOut>): number | undefined {
  return last.meta.page < last.meta.total_pages ? last.meta.page + 1 : undefined;
}

/** Activity in every project the user currently belongs to, newest first, page by page. */
export function useMyActivityFeed() {
  return useInfiniteQuery({
    queryKey: activityKeys.mineFeed(),
    queryFn: ({ pageParam, signal }) =>
      getMyActivity({ page: pageParam, page_size: ACTIVITY_PAGE_SIZE }, signal),
    initialPageParam: 1,
    getNextPageParam: nextPage,
  });
}

/** One project's timeline, newest first, page by page. */
export function useProjectActivityFeed(projectId: string) {
  return useInfiniteQuery({
    queryKey: activityKeys.projectFeed(projectId),
    queryFn: ({ pageParam, signal }) =>
      getProjectActivity(projectId, { page: pageParam, page_size: ACTIVITY_PAGE_SIZE }, signal),
    initialPageParam: 1,
    getNextPageParam: nextPage,
  });
}
