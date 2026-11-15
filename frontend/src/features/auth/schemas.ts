import { z } from "zod";

// Limits mirror RegisterIn and LoginIn in docs/frontend-api-contract.md. The server is the authority.
const email = z
  .string()
  .trim()
  .min(1, "Enter your email address")
  .pipe(z.email("Enter a valid email address").max(255, "Use at most 255 characters"));

export const loginSchema = z.object({
  email,
  // No length rule beyond "present": a wrong short password must get the same generic 401.
  password: z.string().min(1, "Enter your password").max(128, "Use at most 128 characters"),
});

export const registerSchema = z.object({
  name: z.string().trim().min(1, "Enter your name").max(120, "Use at most 120 characters"),
  email,
  password: z.string().min(8, "Use at least 8 characters").max(128, "Use at most 128 characters"),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;
