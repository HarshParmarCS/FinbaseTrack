import { ben, cy, me } from "../projects/fixtures";

export { ben, cy, me };

const OWNER_TASK_ACTIONS = ["update", "complete"];

export function task(id: string, title: string, extra: object = {}) {
  return {
    id,
    project_id: "p1",
    title,
    description: `About ${title}`,
    status: "todo",
    priority: "medium",
    assignee: ben,
    creator: me,
    due_date: "2099-06-30",
    position: 1024,
    completed_at: null,
    allowed_actions: OWNER_TASK_ACTIONS,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-05T12:00:00Z",
    ...extra,
  };
}

export const taskPage = <T>(
  data: T[],
  meta: Partial<{ page: number; total: number; total_pages: number }> = {},
) => ({
  data,
  meta: { page: 1, page_size: 20, total: data.length, total_pages: 1, ...meta },
});
