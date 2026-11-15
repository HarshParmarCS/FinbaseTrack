import type { TaskPriority, TaskSort, TaskStatus } from "@/types/api";

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  completed: "Completed",
};

export const TASK_PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

/**
 * The moves the backend accepts (docs/frontend-api-contract.md, "Transitions only along the line
 * todo <-> in_progress <-> completed"). Used only to avoid offering moves that are certain to be
 * refused; the backend still validates every change.
 */
export const NEXT_STATUSES: Record<TaskStatus, readonly TaskStatus[]> = {
  todo: ["in_progress"],
  in_progress: ["todo", "completed"],
  completed: ["in_progress"],
};

export const TASK_SORT_LABELS: Record<TaskSort, string> = {
  "-created_at": "Newest first",
  created_at: "Oldest first",
  "-updated_at": "Recently updated",
  updated_at: "Least recently updated",
  due_date: "Due date (soonest)",
  "-due_date": "Due date (latest)",
  "-priority": "Priority (high first)",
  priority: "Priority (low first)",
  position: "Board order",
};
