"use client";

import { Calendar, MoreHorizontal, Pencil, Trash2, UserRound, Users } from "lucide-react";
import Link from "next/link";
import { InitialsTile } from "@/components/shared/initials-tile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PROJECT_STATUS_LABELS } from "@/features/projects/status";
import { formatDate } from "@/lib/format";
import type { ProjectOut } from "@/types/api";

type ProjectCardProps = {
  project: ProjectOut;
  currentUserId: string | undefined;
  onEdit: (project: ProjectOut) => void;
  onDelete: (project: ProjectOut) => void;
};

export function ProjectCard({ project, currentUserId, onEdit, onDelete }: ProjectCardProps) {
  // `allowed_actions` is the backend's own answer for this user and project. The backend still
  // enforces every action; this only avoids offering buttons that would be refused.
  const canEdit = project.allowed_actions.includes("update");
  const canDelete = project.allowed_actions.includes("delete");
  const { todo, in_progress, completed } = project.task_counts;
  const owner = project.owner.id === currentUserId ? "You" : project.owner.name;

  return (
    <Card className="relative h-full pt-6 transition-all hover:-translate-y-0.5 hover:shadow-card-hover">
      {/* thin brand accent along the top edge */}
      <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-brand-gradient" />
      <CardContent className="flex h-full flex-col gap-4">
        <div className="flex items-start justify-between gap-2">
          <InitialsTile name={project.name} />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Link
              href={`/projects/${project.id}`}
              className="block truncate text-base font-semibold hover:text-brand-700 hover:underline"
            >
              {project.name}
            </Link>
            <Badge variant={project.status === "active" ? "secondary" : "outline"}>
              {PROJECT_STATUS_LABELS[project.status]}
            </Badge>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${project.name}`}>
                <MoreHorizontal aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem asChild>
                <Link href={`/projects/${project.id}`}>Open</Link>
              </DropdownMenuItem>
              {canEdit ? (
                <DropdownMenuItem onSelect={() => onEdit(project)}>
                  <Pencil aria-hidden />
                  Edit
                </DropdownMenuItem>
              ) : null}
              {canDelete ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive" onSelect={() => onDelete(project)}>
                    <Trash2 aria-hidden />
                    Delete
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">
          {project.description ?? "No description"}
        </p>

        <dl className="mt-auto grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border/70 pt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <UserRound className="size-3.5" aria-hidden />
            <dt className="sr-only">Owner</dt>
            <dd className="truncate">{owner}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <Users className="size-3.5" aria-hidden />
            <dt className="sr-only">Members</dt>
            <dd>
              {project.member_count} {project.member_count === 1 ? "member" : "members"}
            </dd>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="size-3.5" aria-hidden />
            <dt className="sr-only">Created</dt>
            <dd>{formatDate(project.created_at)}</dd>
          </div>
          <div>
            <dt className="sr-only">Tasks</dt>
            <dd>
              {todo + in_progress} open · {completed} done
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
