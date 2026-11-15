import { Badge } from "@/components/ui/badge";
import { describeDue } from "@/features/dashboard/format";
import { isOverdue } from "@/features/dashboard/tasks";
import { cn } from "@/lib/utils";
import type { ProjectOut, TaskOut, TaskPriority } from "@/types/api";

const PRIORITY_VARIANT: Record<TaskPriority, "destructive" | "secondary" | "outline"> = {
  high: "destructive",
  medium: "secondary",
  low: "outline",
};

type TaskRowsProps = {
  tasks: readonly TaskOut[];
  projects: readonly ProjectOut[];
  today: string;
};

/** A compact list of tasks with project name, priority and due date. */
export function TaskRows({ tasks, projects, today }: TaskRowsProps) {
  const names = new Map(projects.map((project) => [project.id, project.name]));
  return (
    <ul className="divide-y">
      {tasks.map((task) => {
        const overdue = isOverdue(task, today);
        return (
          <li key={task.id} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{task.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {names.get(task.project_id) ?? "Project"}
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Badge variant={PRIORITY_VARIANT[task.priority]} className="capitalize">
                {task.priority}
              </Badge>
              <span
                className={cn("text-xs", overdue ? "text-destructive" : "text-muted-foreground")}
              >
                {task.due_date ? describeDue(task.due_date, today) : "No due date"}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
