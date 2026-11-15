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
import { CreateTaskDialog } from "@/features/tasks/create-task-dialog";

export function QuickActions() {
  const [dialog, setDialog] = useState<"project" | "task" | null>(null);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button>
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
      <CreateTaskDialog open={dialog === "task"} onOpenChange={(o) => !o && setDialog(null)} />
    </>
  );
}
