import { z } from "zod";
import { PROJECT_STATUSES } from "@/types/api";

// Limits mirror ProjectCreate, ProjectUpdate and MemberCreate in docs/frontend-api-contract.md.
const name = z
  .string()
  .trim()
  .min(1, "Enter a project name")
  .max(120, "Use at most 120 characters");
const description = z.string().trim().max(5000, "Use at most 5000 characters");

export const createProjectSchema = z.object({ name, description });
export type CreateProjectValues = z.infer<typeof createProjectSchema>;

export const editProjectSchema = z.object({
  name,
  description,
  status: z.enum(PROJECT_STATUSES),
});
export type EditProjectValues = z.infer<typeof editProjectSchema>;

export const addMemberSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter the person's email address")
    .pipe(z.email("Enter a valid email address").max(255, "Use at most 255 characters")),
});
export type AddMemberValues = z.infer<typeof addMemberSchema>;
