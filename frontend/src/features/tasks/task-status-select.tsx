"use client";

import { Loader2 } from "lucide-react";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { useChangeTaskStatus } from "@/features/tasks/hooks";
import { NEXT_STATUSES, TASK_STATUS_LABELS } from "@/features/tasks/status";
import { getActionErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import type { TaskOut, TaskStatus } from "@/types/api";
import { toast } from "sonner";

type Props = {
  task: TaskOut;
  /** Called with a readable message when the backend refuses or fails. */
  onError: (message: string) => void;
  onSuccess?: () => void;
  className?: string;
};

/**
 * Changes a task's status through its own endpoint. The select shows the current status and the
 * moves the backend accepts. It is disabled when the backend does not list "update" for this
 * user, and "Completed" is disabled until the backend lists "complete" (update AND the completion
 * policy). The backend still decides: a refusal comes back as a message through `onError`.
 */
export function TaskStatusSelect({ task, onError, onSuccess, className }: Props) {
  const change = useChangeTaskStatus(task.id);
  const canUpdate = task.allowed_actions.includes("update");
  const canComplete = task.allowed_actions.includes("complete");
  const options: TaskStatus[] = [task.status, ...NEXT_STATUSES[task.status]];

  async function handleChange(next: TaskStatus) {
    if (next === task.status) return;
    try {
      await change.mutateAsync({ status: next });
      toast.success(`“${task.title}” moved to ${TASK_STATUS_LABELS[next]}`);
      onSuccess?.();
    } catch (error) {
      onError(getActionErrorMessage(error));
    }
  }

  return (
    <div className="relative inline-flex items-center">
      <NativeSelect
        aria-label={`Status of ${task.title}`}
        className={cn("w-36", className)}
        value={task.status}
        disabled={!canUpdate || change.isPending}
        onChange={(event) => void handleChange(event.target.value as TaskStatus)}
      >
        {options.map((status) => (
          <NativeSelectOption
            key={status}
            value={status}
            disabled={status === "completed" && status !== task.status && !canComplete}
          >
            {TASK_STATUS_LABELS[status]}
            {status === "completed" && status !== task.status && !canComplete
              ? " (not available yet)"
              : ""}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      {change.isPending ? (
        <Loader2
          className="absolute -right-6 size-4 animate-spin text-muted-foreground"
          aria-hidden
        />
      ) : null}
    </div>
  );
}
