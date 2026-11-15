"use client";

import { History } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { activitySubject, activityVerb } from "@/features/dashboard/activity-text";
import { relativeTime } from "@/features/dashboard/format";
import { useDashboardStats } from "@/features/dashboard/hooks";

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

/** The ten most recent events in the user's projects, as returned with the statistics. */
export function ActivityCard({ now }: { now: Date }) {
  const stats = useDashboardStats();

  let body;
  if (stats.isError) {
    body = (
      <InlineError
        message="Recent activity could not be loaded."
        onRetry={() => void stats.refetch()}
      />
    );
  } else if (!stats.data) {
    body = <ListSkeleton />;
  } else if (stats.data.recent_activity.length === 0) {
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
      <ul className="space-y-3">
        {stats.data.recent_activity.map((activity) => {
          const subject = activitySubject(activity);
          return (
            <li key={activity.id} className="flex items-start gap-3">
              <Avatar size="sm">
                <AvatarFallback>{initials(activity.user.name)}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1 text-sm">
                <p>
                  <span className="font-medium">{activity.user.name}</span>{" "}
                  {activityVerb(activity.action)}
                  {subject ? <span className="text-muted-foreground">: {subject}</span> : null}
                </p>
                <p className="text-xs text-muted-foreground">
                  {relativeTime(activity.created_at, now)}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <SectionCard title="Recent activity" description="Latest changes in your projects">
      {body}
    </SectionCard>
  );
}
