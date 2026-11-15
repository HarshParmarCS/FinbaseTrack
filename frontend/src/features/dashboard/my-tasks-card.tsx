"use client";

import { ListChecks } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { useAuth } from "@/features/auth/auth-provider";
import {
  useDashboardProjects,
  useDashboardStats,
  useOpenTasksAcrossProjects,
} from "@/features/dashboard/hooks";
import { sortByDueDate } from "@/features/dashboard/tasks";
import { TaskRows } from "@/features/dashboard/task-rows";
import type { TaskListParams } from "@/types/api";

const VISIBLE = 8;

export function MyTasksCard({ today }: { today: string }) {
  const { user } = useAuth();
  const projects = useDashboardProjects();
  const stats = useDashboardStats();
  const params: TaskListParams = {
    assignee_id: user?.id,
    status: ["todo", "in_progress"],
    sort: "due_date",
    page_size: 10,
  };
  const mine = useOpenTasksAcrossProjects(projects.data?.data, params);

  const assigned = stats.data?.assigned_to_me;
  const tasks = sortByDueDate(mine.tasks);
  const shown = tasks.slice(0, VISIBLE);
  const partial = mine.skippedProjects > 0 || mine.hasMoreInProjects;

  let body;
  if (projects.isError || mine.isError) {
    body = (
      <InlineError
        message="Your tasks could not be loaded."
        onRetry={() => (projects.isError ? void projects.refetch() : mine.retry())}
      />
    );
  } else if (projects.isPending || mine.isPending) {
    body = <ListSkeleton />;
  } else if (shown.length === 0) {
    body = (
      <EmptyState
        compact
        icon={ListChecks}
        title="Nothing assigned to you"
        description="Tasks assigned to you that are not completed will show up here."
      />
    );
  } else {
    body = <TaskRows tasks={shown} projects={projects.data?.data ?? []} today={today} />;
  }

  return (
    <SectionCard
      title="My assigned tasks"
      description={
        assigned === undefined ? undefined : `${assigned} assigned to you and not completed`
      }
    >
      {body}
      {partial && shown.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Showing the earliest due tasks from the {mine.skippedProjects > 0 ? "first " : ""}
          projects checked. The total above is exact.
        </p>
      ) : null}
    </SectionCard>
  );
}
