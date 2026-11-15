import { isCalendarDate } from "@/lib/format";
import {
  TASK_PRIORITIES,
  TASK_SORTS,
  TASK_STATUSES,
  type TaskListParams,
  type TaskPriority,
  type TaskSort,
  type TaskStatus,
} from "@/types/api";

export const DEFAULT_SORT: TaskSort = "-created_at";
export const UNASSIGNED = "unassigned";
export const TASKS_PAGE_SIZE = 20;

export type TaskFilterState = {
  q: string;
  status: TaskStatus[];
  priority: TaskPriority[];
  /** "" (anyone), "unassigned", or a user id. */
  assignee: string;
  overdue: boolean;
  dueAfter: string;
  dueBefore: string;
  sort: TaskSort;
  page: number;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function onlyValid<T extends string>(values: string[], allowed: readonly T[]): T[] {
  const picked = allowed.filter((candidate) => values.includes(candidate));
  return picked;
}

function validDate(value: string | null): string {
  return value !== null && isCalendarDate(value) ? value : "";
}

/** Read the filters from the URL. Anything invalid is dropped, never sent to the backend. */
export function parseTaskFilters(params: URLSearchParams): TaskFilterState {
  const sort = params.get("sort");
  const page = Number(params.get("page"));
  const assignee = params.get("assignee") ?? "";
  return {
    q: (params.get("q") ?? "").slice(0, 100),
    status: onlyValid(params.getAll("status"), TASK_STATUSES),
    priority: onlyValid(params.getAll("priority"), TASK_PRIORITIES),
    assignee: assignee === UNASSIGNED || UUID.test(assignee) ? assignee : "",
    overdue: params.get("overdue") === "true",
    dueAfter: validDate(params.get("due_after")),
    dueBefore: validDate(params.get("due_before")),
    sort: TASK_SORTS.find((candidate) => candidate === sort) ?? DEFAULT_SORT,
    page: Number.isInteger(page) && page >= 1 ? page : 1,
  };
}

/** The URL form of the filters. Defaults are left out so a clean list has a clean URL. */
export function toSearchParams(state: TaskFilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  for (const status of state.status) params.append("status", status);
  for (const priority of state.priority) params.append("priority", priority);
  if (state.assignee) params.set("assignee", state.assignee);
  if (state.overdue) params.set("overdue", "true");
  if (state.dueAfter) params.set("due_after", state.dueAfter);
  if (state.dueBefore) params.set("due_before", state.dueBefore);
  if (state.sort !== DEFAULT_SORT) params.set("sort", state.sort);
  if (state.page > 1) params.set("page", String(state.page));
  return params;
}

/** The query the backend expects (`GET /projects/{id}/tasks`). */
export function toListParams(state: TaskFilterState, pageSize = TASKS_PAGE_SIZE): TaskListParams {
  return {
    q: state.q || undefined,
    status: state.status.length ? state.status : undefined,
    priority: state.priority.length ? state.priority : undefined,
    assignee_id: state.assignee || undefined,
    overdue: state.overdue ? true : undefined,
    due_after: state.dueAfter || undefined,
    due_before: state.dueBefore || undefined,
    sort: state.sort,
    page: state.page,
    page_size: pageSize,
  };
}

/** True when something other than sort and page narrows the list. */
export function hasActiveFilters(state: TaskFilterState): boolean {
  return Boolean(
    state.q ||
    state.status.length ||
    state.priority.length ||
    state.assignee ||
    state.overdue ||
    state.dueAfter ||
    state.dueBefore,
  );
}

export function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}
