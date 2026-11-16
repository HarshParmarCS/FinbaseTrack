"use client";

import { Compass, ListChecks, Pencil, ShieldAlert, Trash2 } from "lucide-react";
import Link from "next/link";
import { BackLink } from "@/components/shared/back-link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { InlineError } from "@/components/shared/query-states";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";
import { completionPercent } from "@/features/dashboard/format";
import { DeleteProjectDialog } from "@/features/projects/delete-project-dialog";
import { EditProjectDialog } from "@/features/projects/edit-project-dialog";
import { useProject } from "@/features/projects/hooks";
import { MembersSection } from "@/features/projects/members-section";
import { ProjectActivitySection } from "@/features/activity/project-activity-section";
import { PROJECT_STATUS_LABELS } from "@/features/projects/status";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";

const BACK_LINK = <BackLink href={"/projects"}>All projects</BackLink>;

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading project">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export function ProjectDetailView({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const project = useProject(projectId);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState(false);

  if (deleted) return <DetailSkeleton />; // leaving the page; do not refetch a deleted project

  if (project.isError && !project.data) {
    const error = project.error;
    if (isApiError(error) && error.status === 404) {
      // The backend answers 404 for a missing project AND for one the user is not a member of,
      // so existence is not revealed. A project id in the URL grants nothing.
      return (
        <div>
          {BACK_LINK}
          <EmptyState
            icon={Compass}
            title="Project not found"
            description="This project does not exist, or you are not a member of it."
            action={
              <Link href="/projects" className={buttonVariants()}>
                Go to your projects
              </Link>
            }
          />
        </div>
      );
    }
    if (isApiError(error) && error.status === 403) {
      return (
        <div>
          {BACK_LINK}
          <EmptyState
            icon={ShieldAlert}
            title="Permission denied"
            description={`You do not have permission to view this project. ${error.message}`}
          />
        </div>
      );
    }
    return (
      <div>
        {BACK_LINK}
        <InlineError
          message={getErrorMessage(error, "The project could not be loaded.")}
          onRetry={() => void project.refetch()}
        />
      </div>
    );
  }
  if (!project.data) return <DetailSkeleton />;

  const data = project.data;
  const canEdit = data.allowed_actions.includes("update");
  const canDelete = data.allowed_actions.includes("delete");
  const { todo, in_progress, completed } = data.task_counts;
  const total = todo + in_progress + completed;
  const percent = completionPercent(completed, total);

  return (
    <div className="space-y-6">
      <div>
        {BACK_LINK}
        <PageHeader
          eyebrow="Project"
          title={data.name}
          description={data.description ?? "No description"}
          actions={
            <>
              <Badge variant={data.status === "active" ? "secondary" : "outline"}>
                {PROJECT_STATUS_LABELS[data.status]}
              </Badge>
              <Link
                href={`/projects/${data.id}/tasks`}
                className={buttonVariants({ variant: "default" })}
              >
                <ListChecks aria-hidden />
                Tasks
              </Link>
              {canEdit ? (
                <Button variant="outline" onClick={() => setEditing(true)}>
                  <Pencil aria-hidden />
                  Edit
                </Button>
              ) : null}
              {canDelete ? (
                <Button variant="outline" onClick={() => setDeleting(true)}>
                  <Trash2 aria-hidden />
                  Delete
                </Button>
              ) : null}
            </>
          }
        />
      </div>

      <SectionCard title="Overview">
        <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Owner</dt>
            <dd className="font-medium">
              {data.owner.id === user?.id ? "You" : data.owner.name}
              <span className="block truncate text-xs font-normal text-muted-foreground">
                {data.owner.email}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Members</dt>
            <dd className="font-medium">{data.member_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Created</dt>
            <dd className="font-medium">{formatDate(data.created_at)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Last updated</dt>
            <dd className="font-medium">{formatDate(data.updated_at)}</dd>
          </div>
        </dl>
        {percent === null ? (
          <p className="text-sm text-muted-foreground">No tasks yet.</p>
        ) : (
          <div className="space-y-1.5">
            <Progress value={percent} aria-label="Task completion" />
            <p className="text-xs text-muted-foreground">
              {todo} to do · {in_progress} in progress · {completed} completed
            </p>
          </div>
        )}
      </SectionCard>

      <MembersSection project={data} currentUserId={user?.id} />
      <ProjectActivitySection project={data} currentUserId={user?.id} />

      {editing ? (
        <EditProjectDialog project={data} onOpenChange={(open) => !open && setEditing(false)} />
      ) : null}
      {deleting ? (
        <DeleteProjectDialog
          project={data}
          onOpenChange={(open) => !open && setDeleting(false)}
          onDeleted={() => {
            setDeleted(true);
            router.replace("/projects");
          }}
        />
      ) : null}
    </div>
  );
}
