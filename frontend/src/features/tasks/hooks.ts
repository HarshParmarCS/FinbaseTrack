"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { activityKeys } from "@/features/activity/keys";
import { dashboardKeys } from "@/features/dashboard/keys";
import { projectKeys } from "@/features/projects/keys";
import {
  changeTaskStatus,
  createTask,
  deleteTask,
  getTask,
  listTasks,
  updateTask,
} from "@/features/tasks/api";
import { taskKeys } from "@/features/tasks/keys";
import type { TaskCreate, TaskListParams, TaskStatusUpdate, TaskUpdate } from "@/types/api";

export function useTasks(projectId: string, params: TaskListParams = {}) {
  return useQuery({
    queryKey: taskKeys.list(projectId, params),
    queryFn: ({ signal }) => listTasks(projectId, params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: taskKeys.detail(taskId),
    queryFn: ({ signal }) => getTask(taskId, signal),
  });
}

/** A task change also moves project task counts, dashboard statistics and the activity feed. */
function useInvalidateTaskData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: taskKeys.all }),
      queryClient.invalidateQueries({ queryKey: projectKeys.all }),
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all }),
      queryClient.invalidateQueries({ queryKey: activityKeys.all }),
    ]);
}

export function useCreateTask(projectId: string) {
  const invalidate = useInvalidateTaskData();
  return useMutation({
    mutationFn: (input: TaskCreate) => createTask(projectId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateTask(taskId: string) {
  const invalidate = useInvalidateTaskData();
  return useMutation({
    mutationFn: (input: TaskUpdate) => updateTask(taskId, input),
    onSuccess: invalidate,
  });
}

export function useChangeTaskStatus(taskId: string) {
  const invalidate = useInvalidateTaskData();
  return useMutation({
    mutationFn: (input: TaskStatusUpdate) => changeTaskStatus(taskId, input),
    onSuccess: invalidate,
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateTaskData();
  return useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId),
    onSuccess: async (_data, taskId) => {
      queryClient.removeQueries({ queryKey: taskKeys.detail(taskId) });
      await invalidate();
    },
  });
}
