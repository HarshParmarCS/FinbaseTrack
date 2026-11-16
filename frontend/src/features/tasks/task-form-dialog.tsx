"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ListPlus, Loader2, Pencil } from "lucide-react";
import { IconTile } from "@/components/shared/icon-tile";
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
import { useProject } from "@/features/projects/hooks";
import { useCreateTask, useUpdateTask } from "@/features/tasks/hooks";
import { taskFormSchema, type TaskFormValues } from "@/features/tasks/schemas";
import { TASK_PRIORITY_LABELS } from "@/features/tasks/status";
import { buildTaskCreate, buildTaskUpdate, formValuesFor } from "@/features/tasks/update";
import { applyApiError } from "@/lib/api/form-errors";
import {
  TASK_PRIORITIES,
  type MemberOut,
  type ProjectOut,
  type TaskOut,
  type UserOut,
} from "@/types/api";
import { toast } from "sonner";

const FIELDS = ["title", "description", "priority", "assignee_id", "due_date"] as const;

type Props = {
  /** The task's project. Null lets the user choose one of `projectOptions` (new tasks only). */
  projectId: string | null;
  /** Projects to choose from when `projectId` is null: only those that allow create_task. */
  projectOptions?: readonly ProjectOut[];
  /** Present when editing; the dialog creates a task otherwise. */
  task?: TaskOut;
  /**
   * Everyone who can be assigned: the project's members, as the backend returned them. When
   * omitted they are loaded for the chosen project.
   */
  members?: readonly MemberOut[];
  onOpenChange: (open: boolean) => void;
  onSaved?: (task: TaskOut) => void;
};

const EMPTY: TaskFormValues = {
  title: "",
  description: "",
  priority: "medium",
  assignee_id: "",
  due_date: "",
};

/** Mounted only while open, so the form always starts from the task as last loaded. */
export function TaskFormDialog({
  projectId,
  projectOptions = [],
  task,
  members,
  onOpenChange,
  onSaved,
}: Props) {
  const choosing = projectId === null;
  const [chosenProject, setChosenProject] = useState("");
  const [projectError, setProjectError] = useState<string | null>(null);
  const targetProject = projectId ?? chosenProject;
  // The assignable people come from the backend's member list of the target project.
  const loaded = useProject(targetProject, { enabled: !members && targetProject !== "" });
  const people: UserOut[] = (members ?? loaded.data?.members ?? []).map((member) => member.user);
  const create = useCreateTask(targetProject);
  const update = useUpdateTask(task?.id ?? "");
  const pending = create.isPending || update.isPending;
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: task ? formValuesFor(task) : EMPTY,
  });

  // The current assignee stays selectable even if they are no longer in the member list.
  if (task?.assignee && !people.some((person) => person.id === task.assignee?.id)) {
    people.push(task.assignee);
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    if (choosing && !chosenProject) {
      setProjectError("Choose a project");
      return;
    }
    try {
      if (task) {
        const changes = buildTaskUpdate(task, values);
        if (!changes) {
          onOpenChange(false);
          return;
        }
        const saved = await update.mutateAsync(changes);
        toast.success("Task updated");
        onSaved?.(saved);
      } else {
        const saved = await create.mutateAsync(buildTaskCreate(values));
        toast.success(`Task “${saved.title}” created`);
        onSaved?.(saved);
      }
      onOpenChange(false);
    } catch (error) {
      setFormError(applyApiError(error, FIELDS, setError));
    }
  });

  return (
    <Dialog open onOpenChange={(open) => !pending && onOpenChange(open)}>
      <DialogContent>
        <DialogHeader>
          <IconTile icon={task ? Pencil : ListPlus} className="mb-2" />
          <DialogTitle>{task ? "Edit task" : "New task"}</DialogTitle>
          <DialogDescription>
            {task
              ? "Status changes are made from the status selector. Your permissions are checked on save."
              : "The task starts as To do. Your permissions are checked on save."}
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={onSubmit}
          noValidate
          className="space-y-4"
          aria-label={task ? "Edit task" : "New task"}
        >
          {formError ? (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}
          {choosing ? (
            <FormField id="task-project" label="Project" error={projectError ?? undefined}>
              <NativeSelect
                id="task-project"
                className="w-full"
                value={chosenProject}
                disabled={projectOptions.length === 0}
                aria-invalid={Boolean(projectError)}
                aria-describedby={describedBy("task-project", { error: projectError ?? undefined })}
                onChange={(event) => {
                  setChosenProject(event.target.value);
                  setProjectError(null);
                  setValue("assignee_id", ""); // members differ per project
                }}
              >
                <NativeSelectOption value="">
                  {projectOptions.length ? "Choose a project" : "No project allows new tasks"}
                </NativeSelectOption>
                {projectOptions.map((option) => (
                  <NativeSelectOption key={option.id} value={option.id}>
                    {option.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </FormField>
          ) : null}
          <FormField id="task-title" label="Title" error={errors.title?.message}>
            <Input
              id="task-title"
              maxLength={200}
              aria-invalid={Boolean(errors.title)}
              aria-describedby={describedBy("task-title", { error: errors.title?.message })}
              {...register("title")}
            />
          </FormField>
          <FormField id="task-description" label="Description" error={errors.description?.message}>
            <Textarea
              id="task-description"
              rows={4}
              aria-invalid={Boolean(errors.description)}
              aria-describedby={describedBy("task-description", {
                error: errors.description?.message,
              })}
              {...register("description")}
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="task-priority" label="Priority" error={errors.priority?.message}>
              <NativeSelect id="task-priority" className="w-full" {...register("priority")}>
                {TASK_PRIORITIES.map((priority) => (
                  <NativeSelectOption key={priority} value={priority}>
                    {TASK_PRIORITY_LABELS[priority]}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </FormField>
            <FormField id="task-due" label="Due date" error={errors.due_date?.message}>
              <Input
                id="task-due"
                type="date"
                aria-invalid={Boolean(errors.due_date)}
                aria-describedby={describedBy("task-due", { error: errors.due_date?.message })}
                {...register("due_date")}
              />
            </FormField>
          </div>
          <FormField id="task-assignee" label="Assignee" error={errors.assignee_id?.message}>
            <NativeSelect
              id="task-assignee"
              className="w-full"
              disabled={choosing && !chosenProject}
              {...register("assignee_id")}
            >
              <NativeSelectOption value="">Unassigned</NativeSelectOption>
              {people.map((person) => (
                <NativeSelectOption key={person.id} value={person.id}>
                  {person.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending || (choosing && projectOptions.length === 0)}>
              {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              {task ? "Save changes" : "Create task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
