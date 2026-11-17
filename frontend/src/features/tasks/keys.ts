import type { MyTaskListParams, TaskListParams } from "@/types/api";

export const taskKeys = {
  all: ["tasks"] as const,
  lists: () => [...taskKeys.all, "list"] as const,
  list: (projectId: string, params: TaskListParams) =>
    [...taskKeys.lists(), projectId, params] as const,
  /** The caller's assigned tasks; under `all`, so every task change refreshes it. */
  mine: (params: MyTaskListParams) => [...taskKeys.all, "mine", params] as const,
  details: () => [...taskKeys.all, "detail"] as const,
  detail: (taskId: string) => [...taskKeys.details(), taskId] as const,
};
