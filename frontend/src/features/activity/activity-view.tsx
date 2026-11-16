"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/shared/page-header";
import { SectionCard } from "@/components/shared/section-card";
import { ActivityTimeline } from "@/features/activity/activity-timeline";
import { useMyActivityFeed } from "@/features/activity/hooks";
import { useAuth } from "@/features/auth/auth-provider";
import { useDashboardProjects } from "@/features/dashboard/hooks";

export function ActivityView() {
  const { user } = useAuth();
  const feed = useMyActivityFeed();
  const projects = useDashboardProjects();

  const known = useMemo(
    () => ({
      currentUserId: user?.id,
      projects: new Map((projects.data?.data ?? []).map((p) => [p.id, p.name])),
      projectsComplete: projects.data
        ? projects.data.meta.total <= projects.data.data.length
        : false,
      people: new Map<string, string>(user ? [[user.id, user.name]] : []),
    }),
    [user, projects.data],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Timeline"
        title="Activity"
        description="Everything that happened in the projects you belong to, newest first. Your own actions are marked “You”."
      />
      <SectionCard title="Recent activity">
        <ActivityTimeline
          feed={feed}
          known={known}
          namesPending={projects.isPending}
          emptyTitle="No activity yet"
          emptyDescription="Creating projects, adding members and working on tasks will show up here."
        />
      </SectionCard>
    </div>
  );
}
