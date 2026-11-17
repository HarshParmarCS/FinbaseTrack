/**
 * Types mirroring docs/frontend-api-contract.md (generated from the backend's OpenAPI document).
 * Do not add fields here that the backend does not return.
 */

// ---- envelopes -------------------------------------------------------------------------------

export type Envelope<T> = { data: T };

export type PageMeta = { page: number; page_size: number; total: number; total_pages: number };

export type PagedEnvelope<T> = { data: T[]; meta: PageMeta };

export type ErrorDetail = { field?: string | null; message: string; policy_id?: string | null };

export type ErrorBody = {
  code: string;
  message: string;
  details?: ErrorDetail[];
  request_id?: string | null;
};

export type ErrorResponse = { error: ErrorBody };

// ---- enums -----------------------------------------------------------------------------------

export const PROJECT_STATUSES = ["active", "archived"] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const TASK_STATUSES = ["todo", "in_progress", "completed"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_PRIORITIES = ["low", "medium", "high"] as const;
export type TaskPriority = (typeof TASK_PRIORITIES)[number];

export const TASK_SORTS = [
  "created_at",
  "-created_at",
  "updated_at",
  "-updated_at",
  "due_date",
  "-due_date",
  "priority",
  "-priority",
  "position",
] as const;
export type TaskSort = (typeof TASK_SORTS)[number];

export type ProjectAction = "update" | "delete" | "manage_members" | "create_task";
export type TaskAction = "update" | "delete" | "complete";

/** The backend types `action` as a plain string; this list comes from `ActivityAction` there. */
export type ActivityAction =
  | "user.registered"
  | "auth.login"
  | "auth.logout"
  | "auth.refresh_reuse_detected"
  | "project.created"
  | "project.updated"
  | "project.deleted"
  | "member.added"
  | "member.removed"
  | "task.created"
  | "task.updated"
  | "task.status_changed"
  | "task.assigned"
  | "task.unassigned"
  | "task.deleted";

// ---- health and auth -------------------------------------------------------------------------

export type HealthOut = { status: string };

export type UserOut = { id: string; email: string; name: string };

export type RegisterIn = { name: string; email: string; password: string };

export type LoginIn = { email: string; password: string };

// ---- projects and members --------------------------------------------------------------------

export type TaskCountsOut = { todo: number; in_progress: number; completed: number };

export type MemberOut = { user: UserOut; is_owner: boolean; joined_at: string };

export type ProjectOut = {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  owner: UserOut;
  member_count: number;
  task_counts: TaskCountsOut;
  allowed_actions: ProjectAction[];
  created_at: string;
  updated_at: string;
};

export type ProjectDetailOut = ProjectOut & { members: MemberOut[] };

export type ProjectCreate = {
  name: string;
  description?: string | null;
  status?: ProjectStatus;
};

export type ProjectUpdate = {
  name?: string | null;
  description?: string | null;
  status?: ProjectStatus | null;
};

/** Exactly one of `email` or `user_id` (enforced by the backend). */
export type MemberCreate = { email: string; user_id?: never } | { user_id: string; email?: never };

// ---- tasks -----------------------------------------------------------------------------------

export type TaskOut = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: UserOut | null;
  creator: UserOut;
  due_date: string | null;
  position: number;
  completed_at: string | null;
  allowed_actions: TaskAction[];
  created_at: string;
  updated_at: string;
};

export type TaskCreate = {
  title: string;
  description?: string | null;
  priority?: TaskPriority;
  status?: TaskStatus;
  assignee_id?: string | null;
  due_date?: string | null;
};

/** `status` and `position` are rejected here; use `TaskStatusUpdate` instead. */
export type TaskUpdate = {
  title?: string | null;
  description?: string | null;
  priority?: TaskPriority | null;
  assignee_id?: string | null;
  due_date?: string | null;
};

export type TaskStatusUpdate = { status: TaskStatus; position?: number | null };

/** The project of a task in a cross-project list. */
export type TaskProjectOut = { id: string; name: string; status: ProjectStatus };

/** A task returned by `GET /me/tasks`: every `TaskOut` field plus its project. */
export type AssignedTaskOut = TaskOut & { project: TaskProjectOut };

// ---- dashboard and activity ------------------------------------------------------------------

export type ActivityOut = {
  id: string;
  user: UserOut;
  project_id: string | null;
  task_id: string | null;
  action: ActivityAction;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type DashboardStats = {
  total_projects: number;
  active_projects: number;
  total_tasks: number;
  completed_tasks: number;
  pending_tasks: number;
  overdue_tasks: number;
  assigned_to_me: number;
  recent_activity: ActivityOut[];
};

// ---- query parameters ------------------------------------------------------------------------

/** `limit` is an alias of `page_size`; if both are sent they must be equal. */
export type PageParams = { page?: number; page_size?: number; limit?: number };

export type ProjectListParams = PageParams & { q?: string; status?: ProjectStatus };

export type TaskListParams = PageParams & {
  q?: string;
  /** Repeatable: `?status=todo&status=in_progress`. */
  status?: TaskStatus[];
  priority?: TaskPriority[];
  /** A user id, or the literal `unassigned`. */
  assignee_id?: string;
  /** Inclusive, `YYYY-MM-DD`. */
  due_after?: string;
  due_before?: string;
  overdue?: boolean;
  sort?: TaskSort;
};

/** `GET /me/tasks`: the task list filters without the assignee, plus an optional project. */
export type MyTaskListParams = Omit<TaskListParams, "assignee_id"> & { project_id?: string };
