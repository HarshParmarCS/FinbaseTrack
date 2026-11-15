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
import { useDashboardProjects } from "@/features/dashboard/hooks";
import { useCreateTask } from "@/features/tasks/hooks";
import { createTaskSchema, type CreateTaskValues } from "@/features/tasks/schemas";
import { applyApiError } from "@/lib/api/form-errors";
import { TASK_PRIORITIES } from "@/types/api";

const PRIORITY_LABELS = { low: "Low", medium: "Medium", high: "High" } as const;

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

export function CreateTaskDialog({ open, onOpenChange }: Props) {
  const projects = useDashboardProjects();
  const [formError, setFormError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");
  const createTask = useCreateTask(projectId);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<CreateTaskValues>({
    resolver: zodResolver(createTaskSchema),
    defaultValues: { projectId: "", title: "", priority: "medium", dueDate: "" },
  });

  // The backend decides who may create tasks; the list only offers projects it allows.
  const eligible = (projects.data?.data ?? []).filter((project) =>
    project.allowed_actions.includes("create_task"),
  );

  function handleOpenChange(next: boolean) {
    if (!next) {
      reset();
      setProjectId("");
      setFormError(null);
    }
    onOpenChange(next);
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await createTask.mutateAsync({
        title: values.title,
        priority: values.priority,
        ...(values.dueDate ? { due_date: values.dueDate } : {}),
      });
      handleOpenChange(false);
    } catch (error) {
      setFormError(applyApiError(error, ["title", "priority"], setError));
    }
  });

  const noProjects = projects.isSuccess && eligible.length === 0;
  const projectField = register("projectId", { onChange: (e) => setProjectId(e.target.value) });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New task</DialogTitle>
          <DialogDescription>Add a task to one of your projects.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="space-y-4" aria-label="New task">
          {projects.isError ? (
            <Alert variant="destructive" role="alert">
              <AlertDescription>
                Your projects could not be loaded. Close and try again.
              </AlertDescription>
            </Alert>
          ) : null}
          {noProjects ? (
            <Alert role="status">
              <AlertDescription>Create a project first, then add tasks to it.</AlertDescription>
            </Alert>
          ) : null}
          {formError ? (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <FormField id="task-project" label="Project" error={errors.projectId?.message}>
            <NativeSelect
              id="task-project"
              className="w-full"
              disabled={projects.isPending || eligible.length === 0}
              aria-invalid={Boolean(errors.projectId)}
              aria-describedby={describedBy("task-project", { error: errors.projectId?.message })}
              {...projectField}
            >
              <NativeSelectOption value="">
                {projects.isPending ? "Loading projects…" : "Choose a project"}
              </NativeSelectOption>
              {eligible.map((project) => (
                <NativeSelectOption key={project.id} value={project.id}>
                  {project.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
          <FormField id="task-title" label="Title" error={errors.title?.message}>
            <Input
              id="task-title"
              aria-invalid={Boolean(errors.title)}
              aria-describedby={describedBy("task-title", { error: errors.title?.message })}
              {...register("title")}
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="task-priority" label="Priority" error={errors.priority?.message}>
              <NativeSelect id="task-priority" className="w-full" {...register("priority")}>
                {TASK_PRIORITIES.map((priority) => (
                  <NativeSelectOption key={priority} value={priority}>
                    {PRIORITY_LABELS[priority]}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </FormField>
            <FormField id="task-due" label="Due date (optional)" error={errors.dueDate?.message}>
              <Input
                id="task-due"
                type="date"
                aria-invalid={Boolean(errors.dueDate)}
                aria-describedby={describedBy("task-due", { error: errors.dueDate?.message })}
                {...register("dueDate")}
              />
            </FormField>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createTask.isPending || eligible.length === 0}>
              {createTask.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Create task
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
