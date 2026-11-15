"use client";

import { useMemo } from "react";
import { SectionCard } from "@/components/shared/section-card";
import { ActivityTimeline } from "@/features/activity/activity-timeline";
import { useProjectActivityFeed } from "@/features/activity/hooks";
import type { ProjectDetailOut } from "@/types/api";

type Props = { project: ProjectDetailOut; currentUserId: string | undefined };

/** The project's own timeline (GET /projects/{id}/activity). */
export function ProjectActivitySection({ project, currentUserId }: Props) {
  const feed = useProjectActivityFeed(project.id);
  const known = useMemo(
    () => ({
      currentUserId,
      projects: new Map([[project.id, project.name]]),
      projectsComplete: false, // only this project is known here (every entry belongs to it)
      people: new Map(project.members.map((m) => [m.user.id, m.user.name])),
    }),
    [currentUserId, project.id, project.name, project.members],
  );

  return (
    <SectionCard title="Activity" description="Changes to this project, newest first">
      <ActivityTimeline
        feed={feed}
        known={known}
        hideProject
        emptyTitle="No activity yet"
        emptyDescription="Changes to this project will appear here."
      />
    </SectionCard>
  );
}
