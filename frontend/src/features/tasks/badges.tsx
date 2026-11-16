import { Badge } from "@/components/ui/badge";
import { TASK_PRIORITY_LABELS, TASK_STATUS_LABELS } from "@/features/tasks/status";
import { cn } from "@/lib/utils";
import type { TaskPriority, TaskStatus } from "@/types/api";

// Colors come from the status and priority tokens in globals.css.
const STATUS_STYLE: Record<TaskStatus, string> = {
  todo: "bg-status-todo-soft text-status-todo",
  in_progress: "bg-status-in-progress-soft text-status-in-progress",
  completed: "bg-status-completed-soft text-status-completed",
};

const STATUS_DOT: Record<TaskStatus, string> = {
  todo: "bg-status-todo-solid",
  in_progress: "bg-status-in-progress-solid",
  completed: "bg-status-completed-solid",
};

const PRIORITY_STYLE: Record<TaskPriority, string> = {
  low: "bg-priority-low-soft text-priority-low",
  medium: "bg-priority-medium-soft text-priority-medium",
  high: "bg-priority-high-soft text-priority-high",
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return (
    <Badge variant="soft" className={cn(STATUS_STYLE[status])}>
      <span aria-hidden className={cn("size-1.5 rounded-full", STATUS_DOT[status])} />
      {TASK_STATUS_LABELS[status]}
    </Badge>
  );
}

export function TaskPriorityBadge({ priority }: { priority: TaskPriority }) {
  return (
    <Badge variant="soft" className={cn(PRIORITY_STYLE[priority])}>
      {TASK_PRIORITY_LABELS[priority]}
    </Badge>
  );
}
