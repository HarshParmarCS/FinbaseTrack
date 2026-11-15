"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { useDeleteTask } from "@/features/tasks/hooks";
import { getActionErrorMessage } from "@/lib/api/errors";
import { toast } from "sonner";

type Props = {
  task: { id: string; title: string };
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
};

export function DeleteTaskDialog({ task, onOpenChange, onDeleted }: Props) {
  const deleteTask = useDeleteTask();
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setError(null);
    try {
      await deleteTask.mutateAsync(task.id);
      toast.success(`Task “${task.title}” deleted`);
      onDeleted();
    } catch (failure) {
      setError(getActionErrorMessage(failure));
    }
  }

  return (
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title={`Delete “${task.title}”?`}
      description="This permanently deletes the task. This cannot be undone."
      confirmLabel="Delete task"
      onConfirm={() => void confirm()}
      isPending={deleteTask.isPending}
      error={error}
    />
  );
}
