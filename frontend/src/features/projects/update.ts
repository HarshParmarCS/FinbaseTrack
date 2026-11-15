import type { ProjectOut, ProjectUpdate } from "@/types/api";
import type { EditProjectValues } from "@/features/projects/schemas";

/**
 * Only the fields that changed, because the backend updates exactly what it receives. An emptied
 * description is sent as null, which clears it. Returns null when nothing changed.
 */
export function buildProjectUpdate(
  original: Pick<ProjectOut, "name" | "description" | "status">,
  values: EditProjectValues,
): ProjectUpdate | null {
  const update: ProjectUpdate = {};
  if (values.name !== original.name) update.name = values.name;
  if (values.description !== (original.description ?? "")) {
    update.description = values.description === "" ? null : values.description;
  }
  if (values.status !== original.status) update.status = values.status;
  return Object.keys(update).length > 0 ? update : null;
}
