/** Every backend path in one place, relative to `/api/v1`. See docs/frontend-api-contract.md. */

const id = encodeURIComponent;

export const endpoints = {
  health: "/health",
  auth: {
    register: "/auth/register",
    login: "/auth/login",
    refresh: "/auth/refresh",
    logout: "/auth/logout",
    me: "/auth/me",
  },
  projects: {
    list: "/projects",
    detail: (projectId: string) => `/projects/${id(projectId)}`,
    members: (projectId: string) => `/projects/${id(projectId)}/members`,
    member: (projectId: string, userId: string) =>
      `/projects/${id(projectId)}/members/${id(userId)}`,
    tasks: (projectId: string) => `/projects/${id(projectId)}/tasks`,
    activity: (projectId: string) => `/projects/${id(projectId)}/activity`,
  },
  tasks: {
    detail: (taskId: string) => `/tasks/${id(taskId)}`,
    status: (taskId: string) => `/tasks/${id(taskId)}/status`,
  },
  me: {
    tasks: "/me/tasks",
  },
  dashboard: {
    stats: "/dashboard/stats",
    activity: "/dashboard/activity",
  },
} as const;

/** Endpoints that must never trigger the 401 refresh-and-retry (they are the auth flow itself). */
export const AUTH_FLOW_PATHS: ReadonlySet<string> = new Set([
  endpoints.auth.register,
  endpoints.auth.login,
  endpoints.auth.refresh,
  endpoints.auth.logout,
]);
