import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  AssignedTaskOut,
  Envelope,
  MyTaskListParams,
  PagedEnvelope,
  TaskCreate,
  TaskListParams,
  TaskOut,
  TaskStatusUpdate,
  TaskUpdate,
} from "@/types/api";

export function listTasks(projectId: string, params: TaskListParams, signal?: AbortSignal) {
  return api.get<PagedEnvelope<TaskOut>>(endpoints.projects.tasks(projectId), {
    query: params,
    signal,
  });
}

/** Tasks assigned to the current user across all of their projects. */
export function listMyTasks(params: MyTaskListParams, signal?: AbortSignal) {
  return api.get<PagedEnvelope<AssignedTaskOut>>(endpoints.me.tasks, { query: params, signal });
}

export async function getTask(taskId: string, signal?: AbortSignal) {
  return (await api.get<Envelope<TaskOut>>(endpoints.tasks.detail(taskId), { signal })).data;
}

export async function createTask(projectId: string, input: TaskCreate) {
  return (await api.post<Envelope<TaskOut>>(endpoints.projects.tasks(projectId), input)).data;
}

export async function updateTask(taskId: string, input: TaskUpdate) {
  return (await api.patch<Envelope<TaskOut>>(endpoints.tasks.detail(taskId), input)).data;
}

export async function changeTaskStatus(taskId: string, input: TaskStatusUpdate) {
  return (await api.patch<Envelope<TaskOut>>(endpoints.tasks.status(taskId), input)).data;
}

export function deleteTask(taskId: string) {
  return api.delete(endpoints.tasks.detail(taskId));
}
