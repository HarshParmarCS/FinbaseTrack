"use client";

import { FolderKanban } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError, ListSkeleton } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { InitialsTile } from "@/components/shared/initials-tile";
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
            <li key={project.id} className="flex items-center gap-4 py-3.5">
              <InitialsTile name={project.name} />
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <Link
                    href={`/projects/${project.id}`}
                    className="truncate text-sm font-semibold hover:text-brand-700 hover:underline"
                  >
                    {project.name}
                  </Link>
                  <Badge variant={project.status === "active" ? "secondary" : "outline"}>
                    {project.status === "active" ? "Active" : "Archived"}
                  </Badge>
                </div>
                {percent === null ? (
                  <p className="text-xs text-muted-foreground">No tasks yet</p>
                ) : (
                  <div className="space-y-1.5">
                    <Progress value={percent} aria-label={`${project.name} completion`} />
                    <p className="text-xs text-muted-foreground">
                      {completed} of {total} tasks done · {project.member_count}{" "}
                      {project.member_count === 1 ? "member" : "members"}
                    </p>
                  </div>
                )}
              </div>
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
        <Link
          href="/projects"
          className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold whitespace-nowrap text-brand-700 transition-colors hover:bg-brand-100"
        >
          View all
        </Link>
      }
    >
      {body}
    </SectionCard>
  );
}
