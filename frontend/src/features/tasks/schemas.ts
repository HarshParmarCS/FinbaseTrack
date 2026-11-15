import { z } from "zod";
import { TASK_PRIORITIES } from "@/types/api";

// Limits mirror TaskCreate in docs/frontend-api-contract.md.
export const createTaskSchema = z.object({
  projectId: z.string().min(1, "Choose a project"),
  title: z.string().trim().min(1, "Enter a title").max(200, "Use at most 200 characters"),
  priority: z.enum(TASK_PRIORITIES),
  dueDate: z.union([z.literal(""), z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Enter a valid date")]),
});

export type CreateTaskValues = z.infer<typeof createTaskSchema>;
