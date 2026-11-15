import type { FetchMock } from "../api/helpers";
import { reply } from "../api/helpers";

export const me = { id: "u1", email: "ana@example.com", name: "Ana Lopez" };
const ben = { id: "u2", email: "ben@example.com", name: "Ben Carter" };

export const project = (id: string, name: string, extra: object = {}) => ({
  id,
  name,
  description: null,
  status: "active",
  owner: me,
  member_count: 3,
  task_counts: { todo: 2, in_progress: 1, completed: 3 },
  allowed_actions: ["update", "delete", "manage_members", "create_task"],
  created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
  ...extra,
});

export const task = (id: string, title: string, extra: object = {}) => ({
  id,
  project_id: "p1",
  title,
  description: null,
  status: "todo",
  priority: "high",
  assignee: me,
  creator: ben,
  due_date: "2099-01-01",
  position: 1,
  completed_at: null,
  allowed_actions: ["update"],
  created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-01T00:00:00Z",
  ...extra,
});

export const stats = (extra: object = {}) => ({
  total_projects: 2,
  active_projects: 1,
  total_tasks: 8,
  completed_tasks: 5,
  pending_tasks: 3,
  overdue_tasks: 1,
  assigned_to_me: 2,
  recent_activity: [
    {
      id: "a1",
      user: ben,
      project_id: "p1",
      task_id: "t1",
      action: "task.created",
      metadata: { title: "Write copy" },
      created_at: "2026-11-15T08:00:00Z",
    },
  ],
  ...extra,
});

export const paged = <T>(data: T[], total = data.length) => ({
  data,
  meta: { page: 1, page_size: 100, total, total_pages: 1 },
});

export type Backend = {
  stats: () => Response;
  projects: () => Response;
  tasks: (url: URL) => Response;
  post?: (url: URL, body: unknown) => Response;
};

/** Routes every request the dashboard makes to a handler, like the real API would. */
export function serve(fetchMock: FetchMock, backend: Backend) {
  fetchMock.mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://localhost");
    const path = url.pathname;
    if (init?.method === "POST") {
      const body = init.body ? JSON.parse(String(init.body)) : undefined;
      return backend.post
        ? backend.post(url, body)
        : reply(500, { error: { code: "X", message: "x" } });
    }
    if (path === "/api/v1/auth/me") return reply(200, { data: me });
    if (path === "/api/v1/dashboard/stats") return backend.stats();
    if (path === "/api/v1/projects") return backend.projects();
    if (/^\/api\/v1\/projects\/[^/]+\/tasks$/.test(path)) return backend.tasks(url);
    throw new Error(`unexpected request ${path}`);
  });
}

export const urls = (fetchMock: FetchMock) => fetchMock.mock.calls.map(([u]) => String(u));
