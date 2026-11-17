"use client";

import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { InitialsTile } from "@/components/shared/initials-tile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { describeDue, formatDueDate, relativeTime } from "@/features/dashboard/format";
import { isOverdue } from "@/features/dashboard/tasks";
import { TaskPriorityBadge } from "@/features/tasks/badges";
import { TaskStatusSelect } from "@/features/tasks/task-status-select";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AssignedTaskOut } from "@/types/api";

type Props = {
  tasks: readonly AssignedTaskOut[];
  /** Today in UTC as YYYY-MM-DD (the backend's definition of overdue). */
  today: string;
  now: Date;
  currentUserId: string | undefined;
  onEdit: (task: AssignedTaskOut) => void;
  onDelete: (task: AssignedTaskOut) => void;
  onError: (message: string) => void;
  /** A status change succeeded, so an earlier error message no longer applies. */
  onStatusChanged: () => void;
};

const taskHref = (task: AssignedTaskOut) => `/projects/${task.project.id}/tasks/${task.id}`;

/**
 * The current user's assigned tasks: a table from the md breakpoint, cards below it. Controls
 * follow `allowed_actions` from the backend; nothing here decides access.
 */
export function MyTasksList(props: Props) {
  return (
    <>
      <div className="hidden overflow-x-auto rounded-2xl bg-card shadow-card md:block">
        <MyTasksTable {...props} />
      </div>
      <ul className="space-y-3 md:hidden" aria-label="My tasks">
        {props.tasks.map((task) => (
          <li key={task.id}>
            <MyTaskCard task={task} {...props} />
          </li>
        ))}
      </ul>
    </>
  );
}

function MyTasksTable({ tasks, today, now, currentUserId, ...handlers }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="min-w-48">Task</TableHead>
          <TableHead className="min-w-32">Project</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Priority</TableHead>
          <TableHead>Due</TableHead>
          <TableHead>Created by</TableHead>
          <TableHead className="w-10">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => (
          <TableRow key={task.id}>
            <TableCell className="max-w-xs align-top whitespace-normal">
              <Link href={taskHref(task)} className="font-medium hover:underline">
                {task.title}
              </Link>
              <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                {task.description || "No description"}
              </p>
            </TableCell>
            <TableCell className="align-top">
              <ProjectLabel task={task} />
            </TableCell>
            <TableCell className="align-top">
              <TaskStatusSelect
                task={task}
                onError={handlers.onError}
                onSuccess={handlers.onStatusChanged}
              />
            </TableCell>
            <TableCell className="align-top">
              <TaskPriorityBadge priority={task.priority} />
            </TableCell>
            <TableCell className="align-top text-sm whitespace-nowrap">
              <DueLabel task={task} today={today} />
            </TableCell>
            <TableCell className="align-top text-sm">
              {task.creator.id === currentUserId ? "You" : task.creator.name}
              <span className="block text-xs whitespace-nowrap text-muted-foreground">
                {formatDate(task.created_at)}
              </span>
              <span className="block text-xs whitespace-nowrap text-muted-foreground">
                Updated{" "}
                <time dateTime={task.updated_at} title={formatDate(task.updated_at)}>
                  {relativeTime(task.updated_at, now)}
                </time>
              </span>
            </TableCell>
            <TableCell className="align-top">
              <TaskActions task={task} onEdit={handlers.onEdit} onDelete={handlers.onDelete} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function MyTaskCard({
  task,
  today,
  now,
  currentUserId,
  onEdit,
  onDelete,
  onError,
  onStatusChanged,
}: Props & { task: AssignedTaskOut }) {
  return (
    <article className="space-y-3 rounded-2xl bg-card p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={taskHref(task)} className="font-medium hover:underline">
            {task.title}
          </Link>
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {task.description || "No description"}
          </p>
        </div>
        <TaskActions task={task} onEdit={onEdit} onDelete={onDelete} />
      </div>
      <ProjectLabel task={task} />
      <div className="flex flex-wrap items-center gap-2">
        <TaskStatusSelect task={task} onError={onError} onSuccess={onStatusChanged} />
        <TaskPriorityBadge priority={task.priority} />
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Due</dt>
          <dd>
            <DueLabel task={task} today={today} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Created by</dt>
          <dd>{task.creator.id === currentUserId ? "You" : task.creator.name}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Created</dt>
          <dd>{formatDate(task.created_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Updated</dt>
          <dd>
            <time dateTime={task.updated_at}>{relativeTime(task.updated_at, now)}</time>
          </dd>
        </div>
      </dl>
    </article>
  );
}

function ProjectLabel({ task }: { task: AssignedTaskOut }) {
  return (
    <div className="flex items-center gap-2">
      <InitialsTile name={task.project.name} className="size-7 rounded-lg text-[0.65rem]" />
      <div className="min-w-0">
        <Link
          href={`/projects/${task.project.id}`}
          className="block truncate text-sm font-medium hover:underline"
        >
          {task.project.name}
        </Link>
        {task.project.status === "archived" ? (
          <Badge variant="outline" className="mt-0.5 h-5 px-2 text-[0.65rem]">
            Archived
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

function DueLabel({ task, today }: { task: AssignedTaskOut; today: string }) {
  if (task.status === "completed" && task.completed_at) {
    return (
      <span>
        {task.due_date ? formatDueDate(task.due_date) : "No due date"}
        <span className="block text-xs text-status-completed">
          Done {formatDate(task.completed_at)}
        </span>
      </span>
    );
  }
  if (!task.due_date) return <span className="text-muted-foreground">No due date</span>;
  const overdue = isOverdue(task, today);
  return (
    <span className={cn(overdue && "text-destructive")}>
      {formatDueDate(task.due_date)}
      <span className={cn("block text-xs", !overdue && "text-muted-foreground")}>
        {describeDue(task.due_date, today)}
      </span>
    </span>
  );
}

function TaskActions({
  task,
  onEdit,
  onDelete,
}: {
  task: AssignedTaskOut;
  onEdit: (task: AssignedTaskOut) => void;
  onDelete: (task: AssignedTaskOut) => void;
}) {
  const canEdit = task.allowed_actions.includes("update");
  const canDelete = task.allowed_actions.includes("delete");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${task.title}`}>
          <MoreHorizontal aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem asChild>
          <Link href={taskHref(task)}>Open task</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href={`/projects/${task.project.id}`}>Open project</Link>
        </DropdownMenuItem>
        {canEdit ? (
          <DropdownMenuItem onSelect={() => onEdit(task)}>
            <Pencil aria-hidden />
            Edit
          </DropdownMenuItem>
        ) : null}
        {canDelete ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => onDelete(task)}>
              <Trash2 aria-hidden />
              Delete
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
