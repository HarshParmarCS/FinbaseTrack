"use client";

import { ChevronDown, FolderPlus, ListPlus, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CreateProjectDialog } from "@/features/projects/create-project-dialog";
import { useDashboardProjects } from "@/features/dashboard/hooks";
import { TaskFormDialog } from "@/features/tasks/task-form-dialog";

export function QuickActions() {
  const [dialog, setDialog] = useState<"project" | "task" | null>(null);
  const projects = useDashboardProjects();
  // The backend's answer per project: only those listing create_task are offered.
  const taskProjects = (projects.data?.data ?? []).filter((project) =>
    project.allowed_actions.includes("create_task"),
  );

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="border-transparent shadow-glow">
            <Plus aria-hidden />
            New
            <ChevronDown aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem onSelect={() => setDialog("project")}>
            <FolderPlus aria-hidden />
            New project
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setDialog("task")}>
            <ListPlus aria-hidden />
            New task
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <CreateProjectDialog
        open={dialog === "project"}
        onOpenChange={(o) => !o && setDialog(null)}
      />
      {dialog === "task" ? (
        <TaskFormDialog
          projectId={null}
          projectOptions={taskProjects}
          onOpenChange={(open) => !open && setDialog(null)}
        />
      ) : null}
    </>
  );
}
