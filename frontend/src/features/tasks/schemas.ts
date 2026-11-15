import { z } from "zod";
import { isCalendarDate } from "@/lib/format";
import { TASK_PRIORITIES } from "@/types/api";

// Limits mirror TaskCreate in docs/frontend-api-contract.md.
// ---- the task form (create and edit) -------------------------------------------------------
// Field names match the backend's so a 422 `details[].field` lands on the right input.
// Limits mirror TaskCreate and TaskUpdate in docs/frontend-api-contract.md.

export const taskFormSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Enter a title")
    .max(200, "Use at most 200 characters")
    .refine((value) => !value.includes("\u0000"), "Remove the unsupported character"),
  description: z
    .string()
    .trim()
    .max(5000, "Use at most 5000 characters")
    .refine((value) => !value.includes("\u0000"), "Remove the unsupported character"),
  priority: z.enum(TASK_PRIORITIES),
  /** A member's user id, or "" for unassigned. */
  assignee_id: z.string(),
  /** `YYYY-MM-DD`, or "" for no due date. */
  due_date: z.union([z.literal(""), z.string().refine(isCalendarDate, "Enter a valid date")]),
});

export type TaskFormValues = z.infer<typeof taskFormSchema>;
