"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FolderKanban,
  FolderOpen,
  ListChecks,
  PieChart,
  UserCheck,
} from "lucide-react";
import { InlineError } from "@/components/shared/query-states";
import { StatCard } from "@/components/shared/stat-card";
import { useDashboardStats } from "@/features/dashboard/hooks";
import { completionPercent } from "@/features/dashboard/format";

const PLACEHOLDERS = [
  "Total projects",
  "Active projects",
  "Total tasks",
  "Completed",
  "Pending",
  "Overdue",
  "Assigned to me",
  "Completion",
] as const;

export function StatsGrid() {
  const stats = useDashboardStats();

  if (stats.isError) {
    return (
      <InlineError
        message="The statistics could not be loaded."
        onRetry={() => void stats.refetch()}
      />
    );
  }
  if (!stats.data) {
    return (
      <section aria-label="Statistics" className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {PLACEHOLDERS.map((label) => (
          <StatCard key={label} label={label} icon={ListChecks} isLoading />
        ))}
      </section>
    );
  }

  const s = stats.data;
  const percent = completionPercent(s.completed_tasks, s.total_tasks);
  return (
    <section aria-label="Statistics" className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <StatCard label="Total projects" icon={FolderKanban} value={s.total_projects} />
      <StatCard label="Active projects" icon={FolderOpen} value={s.active_projects} />
      <StatCard label="Total tasks" icon={ListChecks} value={s.total_tasks} />
      <StatCard label="Completed" icon={CheckCircle2} value={s.completed_tasks} tone="success" />
      <StatCard label="Pending" icon={Clock} value={s.pending_tasks} hint="To do and in progress" />
      <StatCard
        label="Overdue"
        icon={AlertTriangle}
        value={s.overdue_tasks}
        tone={s.overdue_tasks > 0 ? "danger" : "neutral"}
      />
      <StatCard
        label="Assigned to me"
        icon={UserCheck}
        value={s.assigned_to_me}
        hint="Not completed"
      />
      <StatCard
        label="Completion"
        icon={PieChart}
        tone="highlight"
        value={percent === null ? undefined : `${percent}%`}
        hint={percent === null ? "No tasks yet" : "Of all tasks in your projects"}
      />
    </section>
  );
}
