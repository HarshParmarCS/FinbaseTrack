import type { TaskFormValues } from "@/features/tasks/schemas";
import type { TaskCreate, TaskOut, TaskUpdate } from "@/types/api";

/** The request body for a new task. Empty optional fields are left out. */
export function buildTaskCreate(values: TaskFormValues): TaskCreate {
  return {
    title: values.title,
    priority: values.priority,
    ...(values.description ? { description: values.description } : {}),
    ...(values.assignee_id ? { assignee_id: values.assignee_id } : {}),
    ...(values.due_date ? { due_date: values.due_date } : {}),
  };
}

export function formValuesFor(task: TaskOut): TaskFormValues {
  return {
    title: task.title,
    description: task.description ?? "",
    priority: task.priority,
    assignee_id: task.assignee?.id ?? "",
    due_date: task.due_date ?? "",
  };
}

/**
 * Only the fields that changed, because the backend updates exactly what it receives. Cleared
 * optional fields are sent as null (description, assignee, due date). `status` and `position`
 * are never part of an update: they have their own endpoint. Null when nothing changed.
 */
export function buildTaskUpdate(task: TaskOut, values: TaskFormValues): TaskUpdate | null {
  const before = formValuesFor(task);
  const update: TaskUpdate = {};
  if (values.title !== before.title) update.title = values.title;
  if (values.description !== before.description) update.description = values.description || null;
  if (values.priority !== before.priority) update.priority = values.priority;
  if (values.assignee_id !== before.assignee_id) update.assignee_id = values.assignee_id || null;
  if (values.due_date !== before.due_date) update.due_date = values.due_date || null;
  return Object.keys(update).length > 0 ? update : null;
}
