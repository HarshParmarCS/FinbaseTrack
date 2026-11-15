"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { getDashboardStats } from "@/features/dashboard/api";
import { dashboardKeys } from "@/features/dashboard/keys";
import { useProjects } from "@/features/projects/hooks";
import { listTasks } from "@/features/tasks/api";
import { taskKeys } from "@/features/tasks/keys";
import type { ProjectOut, TaskListParams, TaskOut } from "@/types/api";

export function useDashboardStats() {
  return useQuery({
    queryKey: dashboardKeys.stats(),
    queryFn: ({ signal }) => getDashboardStats(signal),
  });
}

/** The user's projects (one page of the maximum size) for the overview and the distribution. */
export const DASHBOARD_PROJECT_PAGE_SIZE = 100;

export function useDashboardProjects() {
  return useProjects({ page_size: DASHBOARD_PROJECT_PAGE_SIZE });
}

/**
 * The backend has no endpoint that lists tasks across projects, so the dashboard asks each
 * project that still has open work, up to this many (see docs/frontend-api-contract.md, G2).
 */
export const MAX_PROJECTS_QUERIED = 10;

export type OpenTasksResult = {
  tasks: TaskOut[];
  isPending: boolean;
  isError: boolean;
  /** Some projects with open tasks were not asked because of the limit above. */
  skippedProjects: number;
  /** A project had more matching tasks than one page returned. */
  hasMoreInProjects: boolean;
  retry: () => void;
};

export function useOpenTasksAcrossProjects(
  projects: ProjectOut[] | undefined,
  params: TaskListParams,
): OpenTasksResult {
  const withOpenTasks = (projects ?? []).filter(
    (project) => project.task_counts.todo + project.task_counts.in_progress > 0,
  );
  const queried = withOpenTasks.slice(0, MAX_PROJECTS_QUERIED);

  const results = useQueries({
    queries: queried.map((project) => ({
      queryKey: taskKeys.list(project.id, params),
      queryFn: ({ signal }: { signal: AbortSignal }) => listTasks(project.id, params, signal),
    })),
  });

  return {
    tasks: results.flatMap((result) => result.data?.data ?? []),
    isPending: results.some((result) => result.isPending),
    isError: results.some((result) => result.isError),
    skippedProjects: withOpenTasks.length - queried.length,
    hasMoreInProjects: results.some(
      (result) => result.data !== undefined && result.data.meta.total > result.data.data.length,
    ),
    retry: () => results.forEach((result) => result.isError && void result.refetch()),
  };
}
