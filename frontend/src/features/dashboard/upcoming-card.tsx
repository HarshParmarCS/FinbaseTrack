"use client";

import { CalendarClock } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { useDashboardProjects, useOpenTasksAcrossProjects } from "@/features/dashboard/hooks";
import { sortByDueDate } from "@/features/dashboard/tasks";
import { TaskRows } from "@/features/dashboard/task-rows";

const VISIBLE = 6;

export function UpcomingCard({ today }: { today: string }) {
  const projects = useDashboardProjects();
  const upcoming = useOpenTasksAcrossProjects(projects.data?.data, {
    status: ["todo", "in_progress"],
    due_after: today,
    sort: "due_date",
    page_size: 5,
  });
  const shown = sortByDueDate(upcoming.tasks).slice(0, VISIBLE);

  let body;
  if (projects.isError || upcoming.isError) {
    body = (
      <InlineError
        message="Upcoming tasks could not be loaded."
        onRetry={() => (projects.isError ? void projects.refetch() : upcoming.retry())}
      />
    );
  } else if (projects.isPending || upcoming.isPending) {
    body = <ListSkeleton rows={3} />;
  } else if (shown.length === 0) {
    body = (
      <EmptyState
        compact
        icon={CalendarClock}
        title="No upcoming due dates"
        description="Open tasks with a due date from today on will appear here."
      />
    );
  } else {
    body = <TaskRows tasks={shown} projects={projects.data?.data ?? []} today={today} />;
  }

  return (
    <SectionCard
      title="Upcoming due dates"
      description="Open tasks in your projects, earliest first"
    >
      {body}
    </SectionCard>
  );
}
