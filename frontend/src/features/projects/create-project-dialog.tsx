"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FolderPlus, Loader2 } from "lucide-react";
import { useState } from "react";
import { IconTile } from "@/components/shared/icon-tile";
import { useForm } from "react-hook-form";
import { FormField, describedBy } from "@/components/shared/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateProject } from "@/features/projects/hooks";
import { createProjectSchema, type CreateProjectValues } from "@/features/projects/schemas";
import { applyApiError } from "@/lib/api/form-errors";
import type { ProjectDetailOut } from "@/types/api";
import { toast } from "sonner";

const FIELDS = ["name", "description"] as const;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the created project, after the dialog has closed. */
  onCreated?: (project: ProjectDetailOut) => void;
};

export function CreateProjectDialog({ open, onOpenChange, onCreated }: Props) {
  const createProject = useCreateProject();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<CreateProjectValues>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: "", description: "" },
  });

  function handleOpenChange(next: boolean) {
    if (!next) {
      reset();
      setFormError(null);
    }
    onOpenChange(next);
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await createProject.mutateAsync({
        name: values.name,
        ...(values.description ? { description: values.description } : {}),
      });
      handleOpenChange(false);
      toast.success(`Project “${created.name}” created`);
      onCreated?.(created);
    } catch (error) {
      setFormError(applyApiError(error, FIELDS, setError));
    }
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <IconTile icon={FolderPlus} className="mb-2" />
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>You become the owner and can add members later.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="space-y-4" aria-label="New project">
          {formError ? (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}
          <FormField id="project-name" label="Name" error={errors.name?.message}>
            <Input
              id="project-name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy("project-name", { error: errors.name?.message })}
              {...register("name")}
            />
          </FormField>
          <FormField
            id="project-description"
            label="Description (optional)"
            error={errors.description?.message}
          >
            <Textarea
              id="project-description"
              rows={3}
              aria-invalid={Boolean(errors.description)}
              aria-describedby={describedBy("project-description", {
                error: errors.description?.message,
              })}
              {...register("description")}
            />
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Create project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
