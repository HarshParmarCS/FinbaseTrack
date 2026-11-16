"use client";

import { History, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/query-states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ActivityItem } from "@/features/activity/activity-item";
import { groupByDay, learnFromEntries, type Lookups } from "@/features/activity/describe";
import { getActionErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import type { ActivityOut, PagedEnvelope } from "@/types/api";

export type EventKind = "project" | "member" | "task" | "removal" | "account";

/** Which family an action belongs to; deletions and removals share the "removal" color. */
export function eventKind(action: ActivityOut["action"]): EventKind {
  if (action.endsWith(".deleted") || action === "member.removed") return "removal";
  if (action.startsWith("project.")) return "project";
  if (action.startsWith("member.")) return "member";
  if (action.startsWith("task.")) return "task";
  return "account";
}

const DOT_TONE: Record<EventKind, string> = {
  project: "bg-brand-600",
  member: "bg-highlight-500",
  task: "bg-chart-3",
  removal: "bg-danger",
  account: "bg-status-todo-solid",
};

type Feed = {
  data?: { pages: PagedEnvelope<ActivityOut>[] };
  isPending: boolean;
  isError: boolean;
  error: unknown;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
  refetch: () => unknown;
};

type Props = {
  feed: Feed;
  /** Names known from other real responses (projects, members). Entries add their own. */
  known: Pick<Lookups, "currentUserId" | "projects" | "projectsComplete" | "people">;
  /** Keep the skeleton up while those names are still loading, so no entry shows a stand-in. */
  namesPending?: boolean;
  hideProject?: boolean;
  emptyTitle: string;
  emptyDescription: string;
};

export function TimelineSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading activity">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex gap-3">
          <Skeleton className="size-6 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** A day-grouped, newest-first timeline with "Load more", for any activity feed. */
export function ActivityTimeline({
  feed,
  known,
  namesPending = false,
  hideProject,
  emptyTitle,
  emptyDescription,
}: Props) {
  const [now] = useState(() => new Date());
  const entries = useMemo(() => feed.data?.pages.flatMap((page) => page.data) ?? [], [feed.data]);
  const total = feed.data?.pages[0]?.meta.total ?? 0;

  const lookups: Lookups = useMemo(() => {
    const learned = learnFromEntries(entries);
    return {
      currentUserId: known.currentUserId,
      projects: known.projects,
      projectsComplete: known.projectsComplete,
      people: new Map([...learned.people, ...known.people]),
      taskTitles: learned.taskTitles,
      deletedTasks: learned.deletedTasks,
    };
  }, [entries, known]);

  if (feed.isError && !feed.data) {
    return (
      <InlineError
        message={getActionErrorMessage(feed.error, "The activity could not be loaded.")}
        onRetry={() => void feed.refetch()}
      />
    );
  }
  if (feed.isPending || namesPending) return <TimelineSkeleton />;
  if (entries.length === 0) {
    return <EmptyState compact icon={History} title={emptyTitle} description={emptyDescription} />;
  }

  const groups = groupByDay(entries, now);
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.key} aria-labelledby={`day-${group.key}`}>
          <h3
            id={`day-${group.key}`}
            className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
          >
            {group.label}
          </h3>
          <ol className="relative space-y-5 border-l-2 border-brand-100 pl-5">
            {group.entries.map((entry) => (
              <li key={entry.id} className="relative">
                <span
                  aria-hidden
                  data-kind={eventKind(entry.action)}
                  className={cn(
                    "absolute top-2 -left-[26.5px] size-3 rounded-full ring-4 ring-card",
                    DOT_TONE[eventKind(entry.action)],
                  )}
                />
                <ActivityItem entry={entry} lookups={lookups} now={now} hideProject={hideProject} />
              </li>
            ))}
          </ol>
        </section>
      ))}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground" aria-live="polite">
          Showing {Math.min(entries.length, total)} of {total}
        </p>
        {feed.hasNextPage ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => void feed.fetchNextPage()}
            disabled={feed.isFetchingNextPage}
          >
            {feed.isFetchingNextPage ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Load more
          </Button>
        ) : null}
      </div>
      {feed.isError && feed.data ? (
        <p role="alert" className="text-sm text-destructive">
          More activity could not be loaded. {getActionErrorMessage(feed.error)}
        </p>
      ) : null}
    </div>
  );
}
