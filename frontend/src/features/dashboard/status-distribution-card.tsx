"use client";

import { BarChart3 } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { useDashboardProjects } from "@/features/dashboard/hooks";
import { distributionFrom } from "@/features/dashboard/distribution";
import { cn } from "@/lib/utils";

const SEGMENTS = [
  { key: "todo", label: "To do", color: "bg-status-todo-solid" },
  { key: "in_progress", label: "In progress", color: "bg-status-in-progress-solid" },
  { key: "completed", label: "Completed", color: "bg-status-completed-solid" },
] as const;

export function StatusDistributionCard() {
  const projects = useDashboardProjects();
  const distribution = projects.data ? distributionFrom(projects.data) : null;

  let body;
  if (projects.isError) {
    body = (
      <InlineError
        message="Task counts could not be loaded."
        onRetry={() => void projects.refetch()}
      />
    );
  } else if (!projects.data) {
    body = <ListSkeleton rows={2} />;
  } else if (distribution === null) {
    body = (
      <p className="text-sm text-muted-foreground">
        You have more projects than one page holds, so a complete breakdown is not available yet.
        The statistics above are still exact.
      </p>
    );
  } else if (distribution.total === 0) {
    body = (
      <EmptyState
        compact
        icon={BarChart3}
        title="No tasks yet"
        description="Task counts by status appear once tasks exist."
      />
    );
  } else {
    body = (
      <div className="space-y-4">
        <div
          role="img"
          aria-label={SEGMENTS.map((s) => `${s.label}: ${distribution.counts[s.key]}`).join(", ")}
          className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-muted"
        >
          {SEGMENTS.map((segment) =>
            distribution.counts[segment.key] > 0 ? (
              <div
                key={segment.key}
                className={cn(segment.color)}
                style={{
                  width: `${(distribution.counts[segment.key] / distribution.total) * 100}%`,
                }}
              />
            ) : null,
          )}
        </div>
        <ul className="space-y-2">
          {SEGMENTS.map((segment) => (
            <li key={segment.key} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <span className={cn("size-2.5 rounded-full", segment.color)} aria-hidden />
                {segment.label}
              </span>
              <span className="text-muted-foreground tabular-nums">
                {distribution.counts[segment.key]}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <SectionCard title="Task status" description="All tasks in your projects">
      {body}
    </SectionCard>
  );
}
