"use client";

import { Search, X } from "lucide-react";
import { PillTab, PillTabs } from "@/components/shared/pill-tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { toggle } from "@/features/tasks/filters";
import {
  MY_TASK_SORTS,
  MY_TASK_VIEWS,
  MY_TASK_VIEW_LABELS,
  hasActiveMyTaskFilters,
  type MyTaskFilterState,
} from "@/features/tasks/my-tasks-filters";
import { TASK_PRIORITY_LABELS, TASK_SORT_LABELS } from "@/features/tasks/status";
import { TASK_PRIORITIES, type TaskSort } from "@/types/api";

type ProjectOption = { id: string; name: string };

type Props = {
  state: MyTaskFilterState;
  search: string;
  onSearchChange: (value: string) => void;
  /** Changing any filter or the sort goes back to page 1. */
  onChange: (changes: Partial<MyTaskFilterState>) => void;
  onClear: () => void;
  projects: readonly ProjectOption[];
};

export function MyTasksFiltersBar({
  state,
  search,
  onSearchChange,
  onChange,
  onClear,
  projects,
}: Props) {
  return (
    <div className="space-y-3" role="search" aria-label="Filter my tasks">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            aria-label="Search my tasks"
            placeholder="Search title or description"
            maxLength={100}
            className="pl-9"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <NativeSelect
          aria-label="Sort tasks"
          className="w-full sm:w-52"
          value={state.sort}
          onChange={(event) => onChange({ sort: event.target.value as TaskSort })}
        >
          {MY_TASK_SORTS.map((sort) => (
            <NativeSelectOption key={sort} value={sort}>
              {TASK_SORT_LABELS[sort]}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <PillTabs label="Show">
          {MY_TASK_VIEWS.map((view) => (
            <PillTab key={view} pressed={state.view === view} onClick={() => onChange({ view })}>
              {MY_TASK_VIEW_LABELS[view]}
            </PillTab>
          ))}
        </PillTabs>
        <PillTabs label="Priority">
          {TASK_PRIORITIES.map((priority) => (
            <PillTab
              key={priority}
              pressed={state.priority.includes(priority)}
              onClick={() => onChange({ priority: toggle(state.priority, priority) })}
            >
              {TASK_PRIORITY_LABELS[priority]}
            </PillTab>
          ))}
        </PillTabs>
      </div>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Project
          <NativeSelect
            className="w-56"
            value={state.project}
            onChange={(event) => onChange({ project: event.target.value })}
          >
            <NativeSelectOption value="">All projects</NativeSelectOption>
            {projects.map((project) => (
              <NativeSelectOption key={project.id} value={project.id}>
                {project.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Due on or after
          <Input
            type="date"
            className="w-40"
            value={state.dueAfter}
            onChange={(event) => onChange({ dueAfter: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Due on or before
          <Input
            type="date"
            className="w-40"
            value={state.dueBefore}
            onChange={(event) => onChange({ dueBefore: event.target.value })}
          />
        </label>
        <label className="flex h-8 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-[var(--primary)]"
            checked={state.overdue}
            onChange={(event) => onChange({ overdue: event.target.checked })}
          />
          Overdue only
        </label>
        {hasActiveMyTaskFilters(state) ? (
          <Button type="button" variant="ghost" size="sm" onClick={onClear}>
            <X aria-hidden />
            Clear filters
          </Button>
        ) : null}
      </div>
    </div>
  );
}
