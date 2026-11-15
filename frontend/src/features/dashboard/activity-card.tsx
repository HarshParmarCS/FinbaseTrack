"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { History } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { ActivityItem } from "@/features/activity/activity-item";
import { TimelineSkeleton } from "@/features/activity/activity-timeline";
import { learnFromEntries, type Lookups } from "@/features/activity/describe";
import { useAuth } from "@/features/auth/auth-provider";
import { useDashboardProjects, useDashboardStats } from "@/features/dashboard/hooks";

/** The ten most recent events in the user's projects, as returned with the statistics. */
export function ActivityCard({ now }: { now: Date }) {
  const { user } = useAuth();
  const stats = useDashboardStats();
  const projects = useDashboardProjects();
  const [renderedAt] = useState(now);
  const entries = useMemo(() => stats.data?.recent_activity ?? [], [stats.data]);

  const lookups: Lookups = useMemo(() => {
    const learned = learnFromEntries(entries);
    return {
      currentUserId: user?.id,
      projects: new Map((projects.data?.data ?? []).map((p) => [p.id, p.name])),
      projectsComplete: projects.data
        ? projects.data.meta.total <= projects.data.data.length
        : false,
      people: learned.people,
      taskTitles: learned.taskTitles,
      deletedTasks: learned.deletedTasks,
    };
  }, [entries, projects.data, user?.id]);

  let body;
  if (stats.isError) {
    body = (
      <InlineError
        message="Recent activity could not be loaded."
        onRetry={() => void stats.refetch()}
      />
    );
  } else if (!stats.data || projects.isPending) {
    // Wait for project names too, so no entry briefly shows a stand-in name.
    body = <TimelineSkeleton rows={4} />;
  } else if (entries.length === 0) {
    body = (
      <EmptyState
        compact
        icon={History}
        title="No activity yet"
        description="Changes to your projects and tasks will appear here."
      />
    );
  } else {
    body = (
      <ul className="space-y-4">
        {entries.map((entry) => (
          <li key={entry.id}>
            <ActivityItem entry={entry} lookups={lookups} now={renderedAt} timeStyle="relative" />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <SectionCard
      title="Recent activity"
      description="Latest changes in your projects"
      action={
        <Link href="/activity" className="text-xs font-medium text-primary hover:underline">
          View all
        </Link>
      }
    >
      {body}
    </SectionCard>
  );
}
