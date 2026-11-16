"use client";

import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
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
import { describeDue, formatDueDate } from "@/features/dashboard/format";
import { isOverdue } from "@/features/dashboard/tasks";
import { TaskPriorityBadge } from "@/features/tasks/badges";
import { TaskStatusSelect } from "@/features/tasks/task-status-select";
import { cn } from "@/lib/utils";
import type { TaskOut } from "@/types/api";

type Props = {
  tasks: readonly TaskOut[];
  projectId: string;
  /** Today in UTC as YYYY-MM-DD (the backend's definition of overdue). */
  today: string;
  currentUserId: string | undefined;
  onEdit: (task: TaskOut) => void;
  onDelete: (task: TaskOut) => void;
  onError: (message: string) => void;
  /** A status change succeeded, so an earlier error message no longer applies. */
  onStatusChanged: () => void;
};

export function TasksTable({
  tasks,
  projectId,
  today,
  currentUserId,
  onEdit,
  onDelete,
  onError,
  onStatusChanged,
}: Props) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-card shadow-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-56">Task</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Assignee</TableHead>
            <TableHead>Due</TableHead>
            <TableHead className="w-10">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.map((task) => {
            const overdue = isOverdue(task, today);
            const canEdit = task.allowed_actions.includes("update");
            const canDelete = task.allowed_actions.includes("delete");
            return (
              <TableRow key={task.id}>
                <TableCell>
                  <Link
                    href={`/projects/${projectId}/tasks/${task.id}`}
                    className="font-medium hover:underline"
                  >
                    {task.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <TaskStatusSelect task={task} onError={onError} onSuccess={onStatusChanged} />
                </TableCell>
                <TableCell>
                  <TaskPriorityBadge priority={task.priority} />
                </TableCell>
                <TableCell className="text-sm">
                  {task.assignee ? (
                    task.assignee.id === currentUserId ? (
                      "You"
                    ) : (
                      task.assignee.name
                    )
                  ) : (
                    <span className="text-muted-foreground">Unassigned</span>
                  )}
                </TableCell>
                <TableCell className="text-sm whitespace-nowrap">
                  {task.due_date ? (
                    <span className={cn(overdue && "text-destructive")}>
                      {formatDueDate(task.due_date)}
                      {overdue ? (
                        <span className="block text-xs">{describeDue(task.due_date, today)}</span>
                      ) : null}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">No due date</span>
                  )}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Actions for ${task.title}`}
                      >
                        <MoreHorizontal aria-hidden />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem asChild>
                        <Link href={`/projects/${projectId}/tasks/${task.id}`}>Open</Link>
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
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
