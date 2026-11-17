"use client";

import { ListChecks, SearchX } from "lucide-react";
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
import { useProjects } from "@/features/projects/hooks";
import { DeleteTaskDialog } from "@/features/tasks/delete-task-dialog";
import { useMyTasks } from "@/features/tasks/hooks";
import { MyTasksFiltersBar } from "@/features/tasks/my-tasks-filters-bar";
import {
  DEFAULT_MY_TASK_FILTERS,
  MY_TASK_VIEW_LABELS,
  hasActiveMyTaskFilters,
  parseMyTaskFilters,
  toMyTaskListParams,
  toMyTaskSearchParams,
  type MyTaskFilterState,
} from "@/features/tasks/my-tasks-filters";
import { MyTasksList } from "@/features/tasks/my-tasks-list";
import { TaskFormDialog } from "@/features/tasks/task-form-dialog";
import { getActionErrorMessage } from "@/lib/api/errors";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import type { AssignedTaskOut } from "@/types/api";

/** The largest project page the backend serves; used only to fill the project filter. */
const PROJECT_OPTIONS_PAGE_SIZE = 100;

export function MyTasksView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuth();

  // The URL holds the filters, so reload, back and shared links keep them.
  const state = useMemo(
    () => parseMyTaskFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const [search, setSearch] = useState(state.q);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const tasks = useMyTasks(toMyTaskListParams(state));
  const projects = useProjects({ page_size: PROJECT_OPTIONS_PAGE_SIZE });

  function navigate(next: MyTaskFilterState) {
    const query = toMyTaskSearchParams(next).toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  function change(changes: Partial<MyTaskFilterState>) {
    navigate({ ...state, ...changes, page: "page" in changes ? (changes.page ?? 1) : 1 });
  }

  function clearFilters() {
    setSearch("");
    navigate({ ...DEFAULT_MY_TASK_FILTERS, sort: state.sort });
  }

  useEffect(() => {
    if (debouncedSearch !== state.q) navigate({ ...state, q: debouncedSearch, page: 1 });
    // Only a settled search term should navigate; `state` is read fresh inside.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const [editing, setEditing] = useState<AssignedTaskOut | null>(null);
  const [deleting, setDeleting] = useState<AssignedTaskOut | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [now] = useState(() => new Date());
  const today = utcToday(now);

  const filtered = hasActiveMyTaskFilters(state);
  const items = tasks.data?.data ?? [];
  const total = tasks.data?.meta.total;
  const projectOptions = (projects.data?.data ?? []).map(({ id, name }) => ({ id, name }));

  let content;
  if (tasks.isError && !tasks.data) {
    content = (
      <InlineError
        message={getActionErrorMessage(tasks.error, "Your tasks could not be loaded.")}
        onRetry={() => void tasks.refetch()}
      />
    );
  } else if (!tasks.data) {
    content = (
      <div className="space-y-2" aria-busy="true" aria-label="Loading your tasks">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-14 w-full" />
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
          <Button variant="outline" onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={ListChecks}
        title="Nothing assigned to you"
        description="Open tasks assigned to you in any of your projects show up here."
        action={
          <Link href="/projects" className={buttonVariants({ variant: "outline" })}>
            Go to your projects
          </Link>
        }
      />
    );
  } else {
    content = (
      <div aria-busy={tasks.isFetching}>
        <MyTasksList
          tasks={items}
          today={today}
          now={now}
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
      <PageHeader
        eyebrow="Workspace"
        title="My Tasks"
        description={
          total === undefined
            ? "Tasks assigned to you across all projects."
            : `${total} ${total === 1 ? "task" : "tasks"} assigned to you${describeView(state)}`
        }
      />

      <MyTasksFiltersBar
        state={state}
        search={search}
        onSearchChange={setSearch}
        onChange={change}
        onClear={clearFilters}
        projects={projectOptions}
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

      {editing ? (
        <TaskFormDialog
          key={editing.id}
          projectId={editing.project.id}
          task={editing}
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

function describeView(state: MyTaskFilterState): string {
  const narrowed = hasActiveMyTaskFilters({ ...state, view: "open" });
  const view = state.view === "all" ? "" : ` (${MY_TASK_VIEW_LABELS[state.view].toLowerCase()})`;
  return `${view}${narrowed ? " that match your filters" : ""}`;
}
