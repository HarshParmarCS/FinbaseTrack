import type { PagedEnvelope, ProjectOut, TaskCountsOut } from "@/types/api";

export type Distribution = { counts: TaskCountsOut; total: number };

/**
 * Sum of the per-project task counts. The backend only returns counts per project, so the sum is
 * trustworthy only when every project was loaded. Returns null when more projects exist than the
 * page holds, instead of showing a partial total as if it were complete.
 */
export function distributionFrom(page: PagedEnvelope<ProjectOut>): Distribution | null {
  if (page.meta.total > page.data.length) return null;
  const counts = page.data.reduce<TaskCountsOut>(
    (sum, project) => ({
      todo: sum.todo + project.task_counts.todo,
      in_progress: sum.in_progress + project.task_counts.in_progress,
      completed: sum.completed + project.task_counts.completed,
    }),
    { todo: 0, in_progress: 0, completed: 0 },
  );
  return { counts, total: counts.todo + counts.in_progress + counts.completed };
}
