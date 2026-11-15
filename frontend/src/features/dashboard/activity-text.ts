import type { ActivityOut } from "@/types/api";

const VERBS: Record<ActivityOut["action"], string> = {
  "user.registered": "created the account",
  "auth.login": "signed in",
  "auth.logout": "signed out",
  "auth.refresh_reuse_detected": "had a session ended for security",
  "project.created": "created a project",
  "project.updated": "updated a project",
  "project.deleted": "deleted a project",
  "member.added": "added a member",
  "member.removed": "removed a member",
  "task.created": "created a task",
  "task.updated": "updated a task",
  "task.status_changed": "moved a task",
  "task.assigned": "assigned a task",
  "task.unassigned": "unassigned a task",
  "task.deleted": "deleted a task",
};

const STATUS_LABELS: Record<string, string> = {
  todo: "To do",
  in_progress: "In progress",
  completed: "Completed",
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/**
 * The object of the event, taken only from metadata keys the backend actually writes:
 * `title` for tasks, `name` for projects, `from` and `to` for status changes.
 */
export function activitySubject(activity: ActivityOut): string | null {
  const { metadata } = activity;
  const title = text(metadata.title) ?? text(metadata.name);
  const from = text(metadata.from);
  const to = text(metadata.to);
  if (activity.action === "task.status_changed" && to) {
    const move = from
      ? `${STATUS_LABELS[from] ?? from} to ${STATUS_LABELS[to] ?? to}`
      : (STATUS_LABELS[to] ?? to);
    return title ? `${title} (${move})` : move;
  }
  return title;
}

export function activityVerb(action: ActivityOut["action"]): string {
  return VERBS[action] ?? "made a change";
}
