"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { useDeleteProject } from "@/features/projects/hooks";
import { getActionErrorMessage } from "@/lib/api/errors";
import { toast } from "sonner";

type Props = {
  project: { id: string; name: string };
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
};

export function DeleteProjectDialog({ project, onOpenChange, onDeleted }: Props) {
  const deleteProject = useDeleteProject();
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setError(null);
    try {
      await deleteProject.mutateAsync(project.id);
      toast.success(`Project “${project.name}” deleted`);
      onDeleted();
    } catch (failure) {
      setError(getActionErrorMessage(failure));
    }
  }

  return (
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title={`Delete “${project.name}”?`}
      description="This permanently deletes the project together with all of its tasks and members. This cannot be undone."
      confirmLabel="Delete project"
      onConfirm={() => void confirm()}
      isPending={deleteProject.isPending}
      error={error}
    />
  );
}
