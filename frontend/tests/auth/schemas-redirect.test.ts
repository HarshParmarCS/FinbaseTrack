import { describe, expect, it } from "vitest";
import { buildLoginUrl, safeNextPath } from "@/features/auth/redirect";
import { loginSchema, registerSchema } from "@/features/auth/schemas";

const messages = (result: { success: boolean; error?: { issues: { message: string }[] } }) =>
  result.error?.issues.map((i) => i.message) ?? [];

describe("loginSchema", () => {
  it("accepts a valid email and any non-empty password", () => {
    expect(loginSchema.safeParse({ email: " ana@example.com ", password: "x" }).data).toEqual({
      email: "ana@example.com",
      password: "x",
    });
  });

  it("requires both fields", () => {
    const result = loginSchema.safeParse({ email: "", password: "" });

    expect(messages(result)).toEqual(["Enter your email address", "Enter your password"]);
  });

  it("rejects an invalid email and over-long values", () => {
    expect(messages(loginSchema.safeParse({ email: "nope", password: "x" }))).toEqual([
      "Enter a valid email address",
    ]);
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x".repeat(129) }).success).toBe(
      false,
    );
  });
});

describe("registerSchema", () => {
  const valid = { name: "Ana Lopez", email: "ana@example.com", password: "correct-horse" };

  it("accepts the backend's limits", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
    expect(registerSchema.safeParse({ ...valid, password: "12345678" }).success).toBe(true);
    expect(registerSchema.safeParse({ ...valid, name: "n".repeat(120) }).success).toBe(true);
  });

  it("rejects a short password, a blank name and a long name", () => {
    expect(messages(registerSchema.safeParse({ ...valid, password: "1234567" }))).toEqual([
      "Use at least 8 characters",
    ]);
    expect(messages(registerSchema.safeParse({ ...valid, name: "   " }))).toEqual([
      "Enter your name",
    ]);
    expect(registerSchema.safeParse({ ...valid, name: "n".repeat(121) }).success).toBe(false);
  });

  it("trims the name", () => {
    expect(registerSchema.parse({ ...valid, name: "  Ana  " }).name).toBe("Ana");
  });
});

describe("safeNextPath", () => {
  it.each(["/projects", "/projects/abc/tasks/1", "/projects?q=a#top"])("keeps %s", (path) => {
    expect(safeNextPath(path)).toBe(path);
  });

  it.each([
    null,
    undefined,
    "",
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "projects",
    "/login",
    "/login?next=/x",
    "/register",
    "/ok\nSet-Cookie: x=1",
  ])("falls back to the dashboard for %j", (value) => {
    expect(safeNextPath(value)).toBe("/dashboard");
  });
});

describe("buildLoginUrl", () => {
  it("keeps the page the user wanted", () => {
    expect(buildLoginUrl(null, "/projects?q=a")).toBe("/login?next=%2Fprojects%3Fq%3Da");
  });

  it("adds the expiry reason", () => {
    expect(buildLoginUrl("expired", "/projects")).toBe("/login?reason=expired&next=%2Fprojects");
  });

  it("goes to a clean login page after a deliberate sign-out", () => {
    expect(buildLoginUrl("signed-out", "/projects")).toBe("/login");
  });
});
