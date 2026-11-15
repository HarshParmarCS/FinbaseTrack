import { formatDueDate } from "@/features/dashboard/format";
import { TASK_PRIORITY_LABELS, TASK_STATUS_LABELS } from "@/features/tasks/status";
import { PROJECT_STATUS_LABELS } from "@/features/projects/status";
import type { ActivityOut, TaskPriority, TaskStatus } from "@/types/api";

/**
 * Turns activity entries into sentences using only what the backend returned: the entry, its
 * metadata (keys written by app/services/*_service.py) and names already known from other real
 * responses. Nothing is guessed: an unknown name becomes "a task", "a member" and so on.
 */

export type Lookups = {
  currentUserId?: string;
  /** Projects the user can open, id to name. */
  projects: ReadonlyMap<string, string>;
  /**
   * True only when `projects` is the user's COMPLETE project list. Then a missing id really means
   * the project was deleted or the user left it; otherwise the name is simply not known.
   */
  projectsComplete: boolean;
  /** Users seen in real responses (project members, activity actors), id to name. */
  people: ReadonlyMap<string, string>;
  /** Task titles seen in the loaded activity, id to title. */
  taskTitles: ReadonlyMap<string, string>;
  /** Tasks the loaded activity shows as deleted. */
  deletedTasks: ReadonlySet<string>;
};

export type Ref = { label: string; href?: string };

export type Described = {
  actor: string;
  isYou: boolean;
  /** For example "created the task" or "moved". */
  verb: string;
  /** The task or project the entry is about. */
  subject?: Ref;
  /** Words that follow the subject, for example "to In progress". */
  detail?: string;
  /** The project the entry belongs to, when the subject is a task or a member. */
  project?: Ref;
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function pair(value: unknown): [unknown, unknown] | null {
  return Array.isArray(value) && value.length === 2 ? [value[0], value[1]] : null;
}

function changes(metadata: Record<string, unknown>): Record<string, [unknown, unknown]> {
  const raw = metadata.changes;
  if (typeof raw !== "object" || raw === null) return {};
  const result: Record<string, [unknown, unknown]> = {};
  for (const [field, value] of Object.entries(raw)) {
    const parsed = pair(value);
    if (parsed) result[field] = parsed;
  }
  return result;
}

function statusLabel(value: unknown): string | null {
  const key = text(value);
  return key ? (TASK_STATUS_LABELS[key as TaskStatus] ?? key) : null;
}

function priorityLabel(value: unknown): string | null {
  const key = text(value);
  return key ? (TASK_PRIORITY_LABELS[key as TaskPriority] ?? key) : null;
}

function person(id: unknown, lookups: Lookups, unknown: string): string {
  const key = text(id);
  if (!key) return unknown;
  if (key === lookups.currentUserId) return "you";
  return lookups.people.get(key) ?? unknown;
}

function list(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

function describeTaskChanges(diff: Record<string, [unknown, unknown]>): string | undefined {
  const parts: string[] = [];
  for (const [field, [, after]] of Object.entries(diff)) {
    if (field === "title") parts.push("changed the title");
    else if (field === "description") parts.push("changed the description");
    else if (field === "priority" && priorityLabel(after)) {
      parts.push(`set the priority to ${priorityLabel(after)}`);
    } else if (field === "due_date") {
      parts.push(
        text(after)
          ? `set the due date to ${formatDueDate(String(after))}`
          : "removed the due date",
      );
    }
  }
  return parts.length ? list(parts) : undefined;
}

function describeProjectChanges(diff: Record<string, [unknown, unknown]>): string | undefined {
  const parts: string[] = [];
  for (const [field, [, after]] of Object.entries(diff)) {
    if (field === "name" && text(after)) parts.push(`renamed it to “${String(after)}”`);
    else if (field === "status" && text(after)) {
      const label =
        PROJECT_STATUS_LABELS[after as keyof typeof PROJECT_STATUS_LABELS] ?? String(after);
      parts.push(`set the status to ${label}`);
    } else if (field === "description") parts.push("changed the description");
  }
  return parts.length ? list(parts) : undefined;
}

function projectRef(entry: ActivityOut, lookups: Lookups): Ref | undefined {
  if (!entry.project_id) return undefined;
  const name = lookups.projects.get(entry.project_id);
  if (name) return { label: name, href: `/projects/${entry.project_id}` };
  const fromMetadata = text(entry.metadata.name);
  if (fromMetadata) return { label: fromMetadata };
  return { label: lookups.projectsComplete ? "a project you can no longer open" : "a project" };
}

function taskRef(entry: ActivityOut, lookups: Lookups): Ref {
  const id = entry.task_id;
  const label =
    text(entry.metadata.title) ??
    text(changes(entry.metadata).title?.[1]) ??
    (id ? lookups.taskTitles.get(id) : undefined) ??
    "a task";
  const gone =
    !id ||
    entry.action === "task.deleted" ||
    lookups.deletedTasks.has(id) ||
    !entry.project_id ||
    !lookups.projects.has(entry.project_id);
  return gone ? { label } : { label, href: `/projects/${entry.project_id}/tasks/${id}` };
}

export function describeActivity(entry: ActivityOut, lookups: Lookups): Described {
  const isYou = entry.user.id === lookups.currentUserId;
  const base = { actor: isYou ? "You" : entry.user.name, isYou };
  const meta = entry.metadata;
  const project = projectRef(entry, lookups);

  switch (entry.action) {
    case "project.created":
      return { ...base, verb: "created the project", subject: project };
    case "project.updated":
      return {
        ...base,
        verb: "updated the project",
        subject: project,
        detail: describeProjectChanges(changes(meta)),
      };
    case "project.deleted":
      return {
        ...base,
        verb: "deleted the project",
        subject: { label: text(meta.name) ?? "a project" },
      };
    case "member.added":
      return {
        ...base,
        verb: `added ${person(meta.member_user_id, lookups, "a member")} to`,
        subject: project,
      };
    case "member.removed": {
      const count = typeof meta.unassigned_task_count === "number" ? meta.unassigned_task_count : 0;
      return {
        ...base,
        verb: `removed ${person(meta.member_user_id, lookups, "a former member")} from`,
        subject: project,
        detail: count > 0 ? `(${count} ${count === 1 ? "task" : "tasks"} unassigned)` : undefined,
      };
    }
    case "task.created":
      return { ...base, verb: "created the task", subject: taskRef(entry, lookups), project };
    case "task.updated":
      return {
        ...base,
        verb: "updated",
        subject: taskRef(entry, lookups),
        detail: describeTaskChanges(changes(meta)),
        project,
      };
    case "task.status_changed": {
      const from = statusLabel(meta.from);
      const to = statusLabel(meta.to);
      const detail = to
        ? from && from !== to
          ? `from ${from} to ${to}`
          : `within ${to}`
        : undefined;
      return { ...base, verb: "moved", subject: taskRef(entry, lookups), detail, project };
    }
    case "task.assigned":
      return {
        ...base,
        verb: "assigned",
        subject: taskRef(entry, lookups),
        detail: `to ${person(meta.assignee_id, lookups, "a member")}`,
        project,
      };
    case "task.unassigned":
      return {
        ...base,
        verb: "unassigned",
        subject: taskRef(entry, lookups),
        detail:
          meta.reason === "member_removed" ? "because the assignee left the project" : undefined,
        project,
      };
    case "task.deleted":
      return { ...base, verb: "deleted the task", subject: taskRef(entry, lookups), project };
    case "user.registered":
      return { ...base, verb: "created an account" };
    case "auth.login":
      return { ...base, verb: "signed in" };
    case "auth.logout":
      return { ...base, verb: "signed out" };
    case "auth.refresh_reuse_detected":
      return { ...base, verb: "had a session ended for security" };
    default:
      return { ...base, verb: "made a change", subject: project };
  }
}

/** Names and states that the loaded entries themselves reveal (real data only). */
export function learnFromEntries(entries: readonly ActivityOut[]): {
  people: Map<string, string>;
  taskTitles: Map<string, string>;
  deletedTasks: Set<string>;
} {
  const people = new Map<string, string>();
  const taskTitles = new Map<string, string>();
  const deletedTasks = new Set<string>();
  // Entries are newest first, so the first title seen for a task is its latest known title.
  for (const entry of entries) {
    people.set(entry.user.id, entry.user.name);
    if (!entry.task_id) continue;
    if (entry.action === "task.deleted") deletedTasks.add(entry.task_id);
    const title = text(entry.metadata.title) ?? text(changes(entry.metadata).title?.[1]);
    if (title && !taskTitles.has(entry.task_id)) taskTitles.set(entry.task_id, title);
  }
  return { people, taskTitles, deletedTasks };
}

// ---- time -----------------------------------------------------------------------------------

function localDayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

/** "Today", "Yesterday", or a date (with the year only when it is not this year). */
export function dayLabel(iso: string, now: Date): string {
  const date = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (localDayKey(date) === localDayKey(now)) return "Today";
  if (localDayKey(date) === localDayKey(yesterday)) return "Yesterday";
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  }).format(date);
}

export function timeOfDay(iso: string): string {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export function fullTimestamp(iso: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "full", timeStyle: "short" }).format(
    new Date(iso),
  );
}

/**
 * Groups entries by local day, keeping the backend's order (newest first) inside and between
 * groups. Entries repeated across pages (the feed moved while paging) appear once.
 */
export function groupByDay(entries: readonly ActivityOut[], now: Date) {
  const seen = new Set<string>();
  const groups: { label: string; key: string; entries: ActivityOut[] }[] = [];
  for (const entry of entries) {
    if (seen.has(entry.id)) continue;
    seen.add(entry.id);
    const key = localDayKey(new Date(entry.created_at));
    const last = groups.at(-1);
    if (last && last.key === key) last.entries.push(entry);
    else groups.push({ key, label: dayLabel(entry.created_at, now), entries: [entry] });
  }
  return groups;
}
