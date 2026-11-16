"use client";

import { FolderKanban, Plus, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { InlineError } from "@/components/shared/query-states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";
import { CreateProjectDialog } from "@/features/projects/create-project-dialog";
import { DeleteProjectDialog } from "@/features/projects/delete-project-dialog";
import { EditProjectDialog } from "@/features/projects/edit-project-dialog";
import { useProjects } from "@/features/projects/hooks";
import { ProjectCard } from "@/features/projects/project-card";
import { getActionErrorMessage } from "@/lib/api/errors";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { PROJECT_STATUSES, type ProjectOut, type ProjectStatus } from "@/types/api";

const PAGE_SIZE = 12;

function readStatus(value: string | null): ProjectStatus | undefined {
  return PROJECT_STATUSES.find((status) => status === value);
}

function readPage(value: string | null): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

export function ProjectsView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { user } = useAuth();

  // The URL holds the filters, so reload, back and shared links keep them.
  const status = readStatus(params.get("status"));
  const page = readPage(params.get("page"));
  const urlQuery = params.get("q") ?? "";
  const [search, setSearch] = useState(urlQuery);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  function updateUrl(changes: { q?: string; status?: string; page?: number }) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === undefined || value === "" || value === 1) next.delete(key);
      else next.set(key, String(value));
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  useEffect(() => {
    if (debouncedSearch !== urlQuery) updateUrl({ q: debouncedSearch, page: 1 });
    // updateUrl reads the latest params; only a settled search term should trigger it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const projects = useProjects({
    q: urlQuery || undefined,
    status,
    page,
    page_size: PAGE_SIZE,
  });

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProjectOut | null>(null);
  const [deleting, setDeleting] = useState<ProjectOut | null>(null);

  const filtered = Boolean(urlQuery || status);
  const items = projects.data?.data ?? [];

  let content;
  if (projects.isError && !projects.data) {
    content = (
      <InlineError
        message={getActionErrorMessage(projects.error, "Your projects could not be loaded.")}
        onRetry={() => void projects.refetch()}
      />
    );
  } else if (!projects.data) {
    content = (
      <div
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
        aria-busy="true"
        aria-label="Loading projects"
      >
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-44 w-full" />
        ))}
      </div>
    );
  } else if (items.length === 0) {
    content = filtered ? (
      <EmptyState
        icon={Search}
        title="No projects match"
        description="Try a different search or clear the filters."
        action={
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              router.replace(pathname);
            }}
          >
            Clear filters
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={FolderKanban}
        title="No projects yet"
        description="Create a project to start organizing tasks with your team."
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            New project
          </Button>
        }
      />
    );
  } else {
    content = (
      <ul
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
        aria-label="Projects"
        aria-busy={projects.isFetching}
      >
        {items.map((project) => (
          <li key={project.id}>
            <ProjectCard
              project={project}
              currentUserId={user?.id}
              onEdit={setEditing}
              onDelete={setDeleting}
            />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Projects you own or belong to."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            New project
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            aria-label="Search projects"
            placeholder="Search by name"
            maxLength={100}
            className="pl-9"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <NativeSelect
          aria-label="Filter by status"
          className="w-full sm:w-44"
          value={status ?? ""}
          onChange={(event) => updateUrl({ status: event.target.value, page: 1 })}
        >
          <NativeSelectOption value="">All statuses</NativeSelectOption>
          <NativeSelectOption value="active">Active</NativeSelectOption>
          <NativeSelectOption value="archived">Archived</NativeSelectOption>
        </NativeSelect>
      </div>

      {content}

      {projects.data ? (
        <Pagination
          meta={projects.data.meta}
          disabled={projects.isFetching}
          onPageChange={(next) => updateUrl({ page: next })}
        />
      ) : null}

      <CreateProjectDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(created) => router.push(`/projects/${created.id}`)}
      />
      {editing ? (
        <EditProjectDialog
          key={editing.id}
          project={editing}
          onOpenChange={(open) => !open && setEditing(null)}
        />
      ) : null}
      {deleting ? (
        <DeleteProjectDialog
          project={deleting}
          onOpenChange={(open) => !open && setDeleting(null)}
          onDeleted={() => setDeleting(null)}
        />
      ) : null}
    </div>
  );
}
