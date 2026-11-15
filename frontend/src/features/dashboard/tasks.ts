import type { TaskOut } from "@/types/api";

/** Earliest due date first, tasks without a due date last, then by title for a stable order. */
export function sortByDueDate(tasks: readonly TaskOut[]): TaskOut[] {
  return [...tasks].sort((a, b) => {
    if (a.due_date !== b.due_date) {
      if (a.due_date === null) return 1;
      if (b.due_date === null) return -1;
      return a.due_date < b.due_date ? -1 : 1;
    }
    return a.title.localeCompare(b.title);
  });
}

export function isOverdue(task: TaskOut, today: string): boolean {
  return task.due_date !== null && task.due_date < today && task.status !== "completed";
}
