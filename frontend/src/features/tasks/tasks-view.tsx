"use client";

import { ArrowLeft, ClipboardList, Compass, Plus, SearchX, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { Notice } from "@/components/shared/notice";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { InlineError } from "@/components/shared/query-states";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";
import { utcToday } from "@/features/dashboard/format";
import { useProject } from "@/features/projects/hooks";
import { DeleteTaskDialog } from "@/features/tasks/delete-task-dialog";
import {
  DEFAULT_SORT,
  hasActiveFilters,
  parseTaskFilters,
  toListParams,
  toSearchParams,
  type TaskFilterState,
} from "@/features/tasks/filters";
import { useTasks } from "@/features/tasks/hooks";
import { TaskFiltersBar } from "@/features/tasks/task-filters-bar";
import { TaskFormDialog } from "@/features/tasks/task-form-dialog";
import { TasksTable } from "@/features/tasks/tasks-table";
import { getActionErrorMessage, isApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import type { TaskOut } from "@/types/api";

export function TasksView({ projectId }: { projectId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const project = useProject(projectId);

  // The URL holds the filters, so reload, back and shared links keep them.
  const state = useMemo(
    () => parseTaskFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const [search, setSearch] = useState(state.q);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const tasks = useTasks(projectId, toListParams(state));

  function navigate(next: TaskFilterState) {
    const query = toSearchParams(next).toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  function change(changes: Partial<TaskFilterState>) {
    navigate({ ...state, ...changes, page: "page" in changes ? (changes.page ?? 1) : 1 });
  }

  useEffect(() => {
    if (debouncedSearch !== state.q) navigate({ ...state, q: debouncedSearch, page: 1 });
    // Only a settled search term should navigate; `state` is read fresh inside.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<TaskOut | null>(null);
  const [deleting, setDeleting] = useState<TaskOut | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [today] = useState(() => utcToday(new Date()));

  const back = (
    <Link
      href={`/projects/${projectId}`}
      className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "mb-2 -ml-2")}
    >
      <ArrowLeft aria-hidden />
      {project.data?.name ?? "Project"}
    </Link>
  );

  if (project.isError && !project.data) {
    const error = project.error;
    if (isApiError(error) && (error.status === 404 || error.status === 403)) {
      const denied = error.status === 403;
      return (
        <EmptyState
          icon={denied ? ShieldAlert : Compass}
          title={denied ? "Permission denied" : "Project not found"}
          description={
            denied
              ? `You do not have permission to view this project. ${error.message}`
              : "This project does not exist, or you are not a member of it."
          }
          action={
            <Link href="/projects" className={buttonVariants()}>
              Go to your projects
            </Link>
          }
        />
      );
    }
    return (
      <InlineError
        message={getActionErrorMessage(error, "The project could not be loaded.")}
        onRetry={() => void project.refetch()}
      />
    );
  }

  const members = project.data?.members ?? [];
  const people = members.map((member) => member.user);
  // The backend's answer: members may create tasks, others may not.
  const canCreate = project.data?.allowed_actions.includes("create_task") ?? false;
  const filtered = hasActiveFilters(state);
  const items = tasks.data?.data ?? [];

  let content;
  if (tasks.isError && !tasks.data) {
    content = (
      <InlineError
        message={getActionErrorMessage(tasks.error, "The tasks could not be loaded.")}
        onRetry={() => void tasks.refetch()}
      />
    );
  } else if (!tasks.data) {
    content = (
      <div className="space-y-2" aria-busy="true" aria-label="Loading tasks">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>
    );
  } else if (items.length === 0) {
    content = filtered ? (
      <EmptyState
        icon={SearchX}
        title="No tasks match"
        description="Try different filters or clear them."
        action={
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              navigate({
                ...state,
                q: "",
                status: [],
                priority: [],
                assignee: "",
                overdue: false,
                dueAfter: "",
                dueBefore: "",
                page: 1,
              });
            }}
          >
            Clear filters
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={ClipboardList}
        title="No tasks yet"
        description={
          canCreate
            ? "Create the first task for this project."
            : "Nobody has added a task to this project yet."
        }
        action={
          canCreate ? (
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden />
              New task
            </Button>
          ) : undefined
        }
      />
    );
  } else {
    content = (
      <div aria-busy={tasks.isFetching}>
        <TasksTable
          tasks={items}
          projectId={projectId}
          today={today}
          currentUserId={user?.id}
          onEdit={setEditing}
          onDelete={setDeleting}
          onError={setRowError}
          onStatusChanged={() => setRowError(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        {back}
        <PageHeader
          title="Tasks"
          description={
            tasks.data
              ? `${tasks.data.meta.total} ${tasks.data.meta.total === 1 ? "task" : "tasks"}${filtered ? " match" : ""} in ${project.data?.name ?? "this project"}`
              : (project.data?.name ?? "")
          }
          actions={
            canCreate ? (
              <Button onClick={() => setCreating(true)}>
                <Plus aria-hidden />
                New task
              </Button>
            ) : null
          }
        />
      </div>

      <TaskFiltersBar
        state={state}
        search={search}
        onSearchChange={setSearch}
        onChange={change}
        onClear={() => {
          setSearch("");
          navigate({
            ...state,
            q: "",
            status: [],
            priority: [],
            assignee: "",
            overdue: false,
            dueAfter: "",
            dueBefore: "",
            sort: DEFAULT_SORT,
            page: 1,
          });
        }}
        people={people}
      />

      {rowError ? <Notice kind="error">{rowError}</Notice> : null}
      {content}
      {tasks.data ? (
        <Pagination
          meta={tasks.data.meta}
          disabled={tasks.isFetching}
          onPageChange={(page) => change({ page })}
        />
      ) : null}

      {creating ? (
        <TaskFormDialog
          projectId={projectId}
          members={members}
          onOpenChange={(open) => !open && setCreating(false)}
        />
      ) : null}
      {editing ? (
        <TaskFormDialog
          key={editing.id}
          projectId={projectId}
          task={editing}
          members={members}
          onOpenChange={(open) => !open && setEditing(null)}
        />
      ) : null}
      {deleting ? (
        <DeleteTaskDialog
          task={deleting}
          onOpenChange={(open) => !open && setDeleting(null)}
          onDeleted={() => setDeleting(null)}
        />
      ) : null}
    </div>
  );
}
