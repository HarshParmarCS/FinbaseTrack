"use client";

import { ArrowLeft, Compass, Pencil, ShieldAlert, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { Notice } from "@/components/shared/notice";
import { PageHeader } from "@/components/shared/page-header";
import { InlineError } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";
import { describeDue, formatDueDate, utcToday } from "@/features/dashboard/format";
import { isOverdue } from "@/features/dashboard/tasks";
import { useProject } from "@/features/projects/hooks";
import { TaskPriorityBadge, TaskStatusBadge } from "@/features/tasks/badges";
import { DeleteTaskDialog } from "@/features/tasks/delete-task-dialog";
import { useTask } from "@/features/tasks/hooks";
import { TaskFormDialog } from "@/features/tasks/task-form-dialog";
import { TaskStatusSelect } from "@/features/tasks/task-status-select";
import { getActionErrorMessage, isApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{children}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading task">
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

export function TaskDetailView({ projectId, taskId }: { projectId: string; taskId: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const task = useTask(taskId);
  const project = useProject(projectId);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [today] = useState(() => utcToday(new Date()));

  const listHref = `/projects/${projectId}/tasks`;
  const back = (
    <Link
      href={listHref}
      className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "mb-2 -ml-2")}
    >
      <ArrowLeft aria-hidden />
      All tasks
    </Link>
  );

  if (deleted) return <DetailSkeleton />; // leaving the page; do not refetch a deleted task

  if (task.isError && !task.data) {
    const error = task.error;
    if (isApiError(error) && (error.status === 404 || error.status === 403)) {
      const denied = error.status === 403;
      return (
        <div>
          {back}
          <EmptyState
            icon={denied ? ShieldAlert : Compass}
            title={denied ? "Permission denied" : "Task not found"}
            description={
              denied
                ? `You do not have permission to view this task. ${error.message}`
                : "This task does not exist, or you are not a member of its project."
            }
          />
        </div>
      );
    }
    return (
      <div>
        {back}
        <InlineError
          message={getActionErrorMessage(error, "The task could not be loaded.")}
          onRetry={() => void task.refetch()}
        />
      </div>
    );
  }
  if (!task.data) return <DetailSkeleton />;

  const data = task.data;
  // A task id belongs to exactly one project. A URL that pairs it with another project is wrong.
  if (data.project_id !== projectId) {
    return (
      <div>
        {back}
        <EmptyState
          icon={Compass}
          title="Task not found"
          description="This task does not belong to this project."
        />
      </div>
    );
  }

  const canEdit = data.allowed_actions.includes("update");
  const canDelete = data.allowed_actions.includes("delete");
  const overdue = isOverdue(data, today);

  return (
    <div className="space-y-6">
      <div>
        {back}
        <PageHeader
          title={data.title}
          description={project.data ? `In ${project.data.name}` : undefined}
          actions={
            <>
              <TaskStatusBadge status={data.status} />
              {canEdit ? (
                <Button variant="outline" onClick={() => setEditing(true)}>
                  <Pencil aria-hidden />
                  Edit
                </Button>
              ) : null}
              {canDelete ? (
                <Button variant="outline" onClick={() => setDeleting(true)}>
                  <Trash2 aria-hidden />
                  Delete
                </Button>
              ) : null}
            </>
          }
        />
      </div>

      {statusError ? <Notice kind="error">{statusError}</Notice> : null}

      <SectionCard title="Details">
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Status">
            <TaskStatusSelect
              task={data}
              onError={setStatusError}
              onSuccess={() => setStatusError(null)}
            />
            {canEdit &&
            !data.allowed_actions.includes("complete") &&
            data.status !== "completed" ? (
              <span className="mt-1 block text-xs font-normal text-muted-foreground">
                Completing is not available until the task has an assignee and all required details.
              </span>
            ) : null}
          </Field>
          <Field label="Priority">
            <TaskPriorityBadge priority={data.priority} />
          </Field>
          <Field label="Assignee">
            {data.assignee ? (
              <>
                {data.assignee.id === user?.id ? "You" : data.assignee.name}
                <span className="block truncate text-xs font-normal text-muted-foreground">
                  {data.assignee.email}
                </span>
              </>
            ) : (
              <span className="font-normal text-muted-foreground">Unassigned</span>
            )}
          </Field>
          <Field label="Due date">
            {data.due_date ? (
              <span className={cn(overdue && "text-destructive")}>
                {formatDueDate(data.due_date)} · {describeDue(data.due_date, today)}
              </span>
            ) : (
              <span className="font-normal text-muted-foreground">No due date</span>
            )}
          </Field>
          <Field label="Created by">
            {data.creator.id === user?.id ? "You" : data.creator.name}
          </Field>
          <Field label="Created">{formatDate(data.created_at)}</Field>
          <Field label="Last updated">{formatDate(data.updated_at)}</Field>
          {data.completed_at ? (
            <Field label="Completed">{formatDate(data.completed_at)}</Field>
          ) : null}
        </dl>
        <div>
          <h3 className="mb-1 text-xs text-muted-foreground">Description</h3>
          {data.description ? (
            <p className="text-sm whitespace-pre-wrap">{data.description}</p>
          ) : (
            <p className="text-sm text-muted-foreground">No description</p>
          )}
        </div>
        {!canEdit && !canDelete ? (
          <p className="text-xs text-muted-foreground">You have read-only access to this task.</p>
        ) : null}
      </SectionCard>

      {editing ? (
        <TaskFormDialog
          projectId={projectId}
          task={data}
          members={project.data?.members ?? []}
          onOpenChange={(open) => !open && setEditing(false)}
        />
      ) : null}
      {deleting ? (
        <DeleteTaskDialog
          task={data}
          onOpenChange={(open) => !open && setDeleting(false)}
          onDeleted={() => {
            setDeleted(true);
            router.replace(listHref);
          }}
        />
      ) : null}
    </div>
  );
}
