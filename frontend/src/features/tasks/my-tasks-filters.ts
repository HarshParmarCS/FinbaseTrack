/**
 * Filters of the My Tasks page (`GET /me/tasks`), kept in the URL so reload, back and shared
 * links keep them. Pure functions, tested without rendering.
 */
import { isCalendarDate } from "@/lib/format";
import {
  TASK_PRIORITIES,
  TASK_SORTS,
  type MyTaskListParams,
  type TaskPriority,
  type TaskSort,
  type TaskStatus,
} from "@/types/api";

/** Which statuses to show. "open" (to do and in progress) is the default. */
export const MY_TASK_VIEWS = ["open", "todo", "in_progress", "completed", "all"] as const;
export type MyTaskView = (typeof MY_TASK_VIEWS)[number];

export const MY_TASK_VIEW_LABELS: Record<MyTaskView, string> = {
  open: "Open",
  todo: "To do",
  in_progress: "In progress",
  completed: "Completed",
  all: "All",
};

const VIEW_STATUSES: Record<MyTaskView, TaskStatus[] | undefined> = {
  open: ["todo", "in_progress"],
  todo: ["todo"],
  in_progress: ["in_progress"],
  completed: ["completed"],
  all: undefined,
};

/** Board order means nothing across projects, so it is not offered here. */
export const MY_TASK_SORTS = TASK_SORTS.filter((sort) => sort !== "position");
export const MY_TASKS_DEFAULT_SORT: TaskSort = "due_date";
export const MY_TASKS_PAGE_SIZE = 20;

export type MyTaskFilterState = {
  q: string;
  view: MyTaskView;
  priority: TaskPriority[];
  /** "" (every project) or a project id. */
  project: string;
  overdue: boolean;
  dueAfter: string;
  dueBefore: string;
  sort: TaskSort;
  page: number;
};

export const DEFAULT_MY_TASK_FILTERS: MyTaskFilterState = {
  q: "",
  view: "open",
  priority: [],
  project: "",
  overdue: false,
  dueAfter: "",
  dueBefore: "",
  sort: MY_TASKS_DEFAULT_SORT,
  page: 1,
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function validDate(value: string | null): string {
  return value !== null && isCalendarDate(value) ? value : "";
}

/** Read the filters from the URL. Anything invalid falls back to the default. */
export function parseMyTaskFilters(params: URLSearchParams): MyTaskFilterState {
  const view = params.get("view");
  const sort = params.get("sort");
  const page = Number(params.get("page"));
  const project = params.get("project") ?? "";
  const priorities = params.getAll("priority");
  return {
    q: (params.get("q") ?? "").slice(0, 100),
    view: MY_TASK_VIEWS.find((candidate) => candidate === view) ?? "open",
    priority: TASK_PRIORITIES.filter((candidate) => priorities.includes(candidate)),
    project: UUID.test(project) ? project : "",
    overdue: params.get("overdue") === "true",
    dueAfter: validDate(params.get("due_after")),
    dueBefore: validDate(params.get("due_before")),
    sort: MY_TASK_SORTS.find((candidate) => candidate === sort) ?? MY_TASKS_DEFAULT_SORT,
    page: Number.isInteger(page) && page >= 1 ? page : 1,
  };
}

/** The URL form. Defaults are left out so the plain page has a clean URL. */
export function toMyTaskSearchParams(state: MyTaskFilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.view !== "open") params.set("view", state.view);
  for (const priority of state.priority) params.append("priority", priority);
  if (state.project) params.set("project", state.project);
  if (state.overdue) params.set("overdue", "true");
  if (state.dueAfter) params.set("due_after", state.dueAfter);
  if (state.dueBefore) params.set("due_before", state.dueBefore);
  if (state.sort !== MY_TASKS_DEFAULT_SORT) params.set("sort", state.sort);
  if (state.page > 1) params.set("page", String(state.page));
  return params;
}

/** The query the backend expects (`GET /me/tasks`). */
export function toMyTaskListParams(
  state: MyTaskFilterState,
  pageSize = MY_TASKS_PAGE_SIZE,
): MyTaskListParams {
  return {
    q: state.q || undefined,
    status: VIEW_STATUSES[state.view],
    priority: state.priority.length ? state.priority : undefined,
    project_id: state.project || undefined,
    overdue: state.overdue ? true : undefined,
    due_after: state.dueAfter || undefined,
    due_before: state.dueBefore || undefined,
    sort: state.sort,
    page: state.page,
    page_size: pageSize,
  };
}

/** True when something other than the default view, sort and page narrows the list. */
export function hasActiveMyTaskFilters(state: MyTaskFilterState): boolean {
  return Boolean(
    state.q ||
    state.view !== "open" ||
    state.priority.length ||
    state.project ||
    state.overdue ||
    state.dueAfter ||
    state.dueBefore,
  );
}
