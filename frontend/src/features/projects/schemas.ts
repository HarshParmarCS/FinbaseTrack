import { z } from "zod";

// Limits mirror ProjectCreate in docs/frontend-api-contract.md.
export const createProjectSchema = z.object({
  name: z.string().trim().min(1, "Enter a project name").max(120, "Use at most 120 characters"),
  description: z.string().trim().max(5000, "Use at most 5000 characters"),
});

export type CreateProjectValues = z.infer<typeof createProjectSchema>;
