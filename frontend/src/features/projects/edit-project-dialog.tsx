"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
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
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateProject } from "@/features/projects/hooks";
import { editProjectSchema, type EditProjectValues } from "@/features/projects/schemas";
import { PROJECT_STATUS_LABELS } from "@/features/projects/status";
import { buildProjectUpdate } from "@/features/projects/update";
import { applyApiError } from "@/lib/api/form-errors";
import { PROJECT_STATUSES, type ProjectOut } from "@/types/api";
import { toast } from "sonner";

const FIELDS = ["name", "description", "status"] as const;

type Props = { project: ProjectOut; onOpenChange: (open: boolean) => void };

/** Mounted only while editing, so the form always starts from the project as last loaded. */
export function EditProjectDialog({ project, onOpenChange }: Props) {
  const updateProject = useUpdateProject(project.id);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<EditProjectValues>({
    resolver: zodResolver(editProjectSchema),
    defaultValues: {
      name: project.name,
      description: project.description ?? "",
      status: project.status,
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    const update = buildProjectUpdate(project, values);
    if (!update) {
      onOpenChange(false);
      return;
    }
    try {
      await updateProject.mutateAsync(update);
      toast.success("Project updated");
      onOpenChange(false);
    } catch (error) {
      setFormError(applyApiError(error, FIELDS, setError));
    }
  });

  return (
    <Dialog open onOpenChange={(open) => !updateProject.isPending && onOpenChange(open)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit project</DialogTitle>
          <DialogDescription>
            Changes are checked against your permissions on save.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="space-y-4" aria-label="Edit project">
          {formError ? (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}
          <FormField id="edit-name" label="Name" error={errors.name?.message}>
            <Input
              id="edit-name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy("edit-name", { error: errors.name?.message })}
              {...register("name")}
            />
          </FormField>
          <FormField id="edit-description" label="Description" error={errors.description?.message}>
            <Textarea
              id="edit-description"
              rows={4}
              aria-invalid={Boolean(errors.description)}
              aria-describedby={describedBy("edit-description", {
                error: errors.description?.message,
              })}
              {...register("description")}
            />
          </FormField>
          <FormField id="edit-status" label="Status" error={errors.status?.message}>
            <NativeSelect id="edit-status" className="w-full" {...register("status")}>
              {PROJECT_STATUSES.map((status) => (
                <NativeSelectOption key={status} value={status}>
                  {PROJECT_STATUS_LABELS[status]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateProject.isPending}>
              {updateProject.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
