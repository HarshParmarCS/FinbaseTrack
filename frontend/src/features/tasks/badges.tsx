import { Badge } from "@/components/ui/badge";
import { TASK_PRIORITY_LABELS, TASK_STATUS_LABELS } from "@/features/tasks/status";
import { cn } from "@/lib/utils";
import type { TaskPriority, TaskStatus } from "@/types/api";

const STATUS_STYLE: Record<TaskStatus, string> = {
  todo: "border-transparent bg-slate-100 text-slate-700",
  in_progress: "border-transparent bg-indigo-50 text-indigo-700",
  completed: "border-transparent bg-emerald-50 text-emerald-700",
};

const PRIORITY_STYLE: Record<TaskPriority, string> = {
  low: "border-transparent bg-slate-100 text-slate-600",
  medium: "border-transparent bg-amber-50 text-amber-700",
  high: "border-transparent bg-red-50 text-red-700",
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return (
    <Badge variant="outline" className={cn(STATUS_STYLE[status])}>
      {TASK_STATUS_LABELS[status]}
    </Badge>
  );
}

export function TaskPriorityBadge({ priority }: { priority: TaskPriority }) {
  return (
    <Badge variant="outline" className={cn(PRIORITY_STYLE[priority])}>
      {TASK_PRIORITY_LABELS[priority]}
    </Badge>
  );
}
