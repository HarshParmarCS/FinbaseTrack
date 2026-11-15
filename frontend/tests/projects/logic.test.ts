import { describe, expect, it } from "vitest";
import { ApiError, getActionErrorMessage, isPermissionDenied } from "@/lib/api/errors";
import {
  addMemberSchema,
  createProjectSchema,
  editProjectSchema,
} from "@/features/projects/schemas";
import { buildProjectUpdate } from "@/features/projects/update";
import { formatDate, initials } from "@/lib/format";

const denied = new ApiError({
  status: 403,
  code: "FORBIDDEN",
  message: "Only the project owner can delete a project.",
  details: [
    {
      field: null,
      message: "Only the project owner can delete a project.",
      policy_id: "project-delete",
    },
  ],
});
const csrf = new ApiError({
  status: 403,
  code: "FORBIDDEN",
  message: "CSRF token missing or invalid.",
});

describe("permission errors", () => {
  it("recognizes a policy denial by its policy id", () => {
    expect(isPermissionDenied(denied)).toBe(true);
  });

  it("does not call a CSRF failure a permission problem", () => {
    expect(isPermissionDenied(csrf)).toBe(false);
    expect(getActionErrorMessage(csrf)).toBe("CSRF token missing or invalid.");
  });

  it("does not treat other statuses as permission denials", () => {
    expect(isPermissionDenied(new ApiError({ status: 404, code: "NOT_FOUND", message: "x" }))).toBe(
      false,
    );
    expect(isPermissionDenied(new Error("x"))).toBe(false);
  });

  it("says plainly that permission is missing and keeps the backend's reason", () => {
    expect(getActionErrorMessage(denied)).toBe(
      "You do not have permission to do this. Only the project owner can delete a project.",
    );
  });

  it("falls back for unknown errors", () => {
    expect(getActionErrorMessage(new Error("internal"), "Try again")).toBe("Try again");
  });
});

describe("buildProjectUpdate", () => {
  const original = { name: "Site", description: "Old text", status: "active" as const };
  const same = { name: "Site", description: "Old text", status: "active" as const };

  it("returns null when nothing changed", () => {
    expect(buildProjectUpdate(original, same)).toBeNull();
  });

  it("sends only the fields that changed", () => {
    expect(buildProjectUpdate(original, { ...same, name: "New" })).toEqual({ name: "New" });
    expect(buildProjectUpdate(original, { ...same, status: "archived" })).toEqual({
      status: "archived",
    });
  });

  it("clears the description with null, which the backend treats as 'remove it'", () => {
    expect(buildProjectUpdate(original, { ...same, description: "" })).toEqual({
      description: null,
    });
  });

  it("treats a missing description and an empty field as the same", () => {
    expect(
      buildProjectUpdate({ ...original, description: null }, { ...same, description: "" }),
    ).toBeNull();
    expect(
      buildProjectUpdate({ ...original, description: null }, { ...same, description: "Hi" }),
    ).toEqual({
      description: "Hi",
    });
  });
});

describe("project schemas", () => {
  it("accepts the backend's limits and trims text", () => {
    expect(createProjectSchema.parse({ name: "  Site  ", description: "" }).name).toBe("Site");
    expect(
      createProjectSchema.safeParse({ name: "n".repeat(120), description: "d".repeat(5000) })
        .success,
    ).toBe(true);
  });

  it("rejects blank, over-long and invalid values", () => {
    expect(createProjectSchema.safeParse({ name: "  ", description: "" }).success).toBe(false);
    expect(createProjectSchema.safeParse({ name: "n".repeat(121), description: "" }).success).toBe(
      false,
    );
    expect(
      createProjectSchema.safeParse({ name: "x", description: "d".repeat(5001) }).success,
    ).toBe(false);
    expect(
      editProjectSchema.safeParse({ name: "x", description: "", status: "deleted" }).success,
    ).toBe(false);
  });

  it("requires a valid email to add a member", () => {
    expect(addMemberSchema.safeParse({ email: " ben@example.com " }).data).toEqual({
      email: "ben@example.com",
    });
    expect(addMemberSchema.safeParse({ email: "" }).success).toBe(false);
    expect(addMemberSchema.safeParse({ email: "ben" }).success).toBe(false);
  });
});

describe("format helpers", () => {
  it("takes up to two initials", () => {
    expect(initials("Ana Maria Lopez")).toBe("AM");
    expect(initials("ben")).toBe("B");
    expect(initials("   ")).toBe("?");
  });

  it("formats a timestamp as a short date", () => {
    expect(formatDate("2026-11-15T12:00:00Z")).toBe("Nov 15, 2026");
  });
});
