"use client";

import { FolderKanban } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { completionPercent } from "@/features/dashboard/format";
import { useDashboardProjects } from "@/features/dashboard/hooks";

const VISIBLE = 6;

export function ProjectsOverviewCard() {
  const projects = useDashboardProjects();

  let body;
  if (projects.isError) {
    body = (
      <InlineError
        message="Your projects could not be loaded."
        onRetry={() => void projects.refetch()}
      />
    );
  } else if (!projects.data) {
    body = <ListSkeleton />;
  } else if (projects.data.data.length === 0) {
    body = (
      <EmptyState
        compact
        icon={FolderKanban}
        title="No projects yet"
        description="Use New in the header to create your first project."
      />
    );
  } else {
    body = (
      <ul className="divide-y">
        {projects.data.data.slice(0, VISIBLE).map((project) => {
          const { todo, in_progress, completed } = project.task_counts;
          const total = todo + in_progress + completed;
          const percent = completionPercent(completed, total);
          return (
            <li key={project.id} className="space-y-2 py-3">
              <div className="flex items-center justify-between gap-3">
                <Link
                  href={`/projects/${project.id}`}
                  className="truncate text-sm font-medium hover:underline"
                >
                  {project.name}
                </Link>
                {project.status === "archived" ? <Badge variant="outline">Archived</Badge> : null}
              </div>
              {percent === null ? (
                <p className="text-xs text-muted-foreground">No tasks yet</p>
              ) : (
                <div className="space-y-1">
                  <Progress value={percent} aria-label={`${project.name} completion`} />
                  <p className="text-xs text-muted-foreground">
                    {completed} of {total} tasks done · {project.member_count}{" "}
                    {project.member_count === 1 ? "member" : "members"}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <SectionCard
      title="Project overview"
      description="Most recently updated first"
      action={
        <Link href="/projects" className="text-xs font-medium text-primary hover:underline">
          View all
        </Link>
      }
    >
      {body}
    </SectionCard>
  );
}
