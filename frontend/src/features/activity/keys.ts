import type { PageParams } from "@/types/api";

export const activityKeys = {
  all: ["activity"] as const,
  mine: (params: PageParams) => [...activityKeys.all, "mine", params] as const,
  project: (projectId: string, params: PageParams) =>
    [...activityKeys.all, "project", projectId, params] as const,
  /** "Load more" feeds (infinite queries). */
  mineFeed: () => [...activityKeys.all, "mine", "feed"] as const,
  projectFeed: (projectId: string) => [...activityKeys.all, "project", projectId, "feed"] as const,
};
