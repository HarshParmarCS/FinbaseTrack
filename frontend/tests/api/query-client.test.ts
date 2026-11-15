import { describe, expect, it } from "vitest";
import { createQueryClient, shouldRetry } from "@/lib/api/query-client";
import { ApiError } from "@/lib/api/errors";
import { activityKeys } from "@/features/activity/keys";
import { authKeys } from "@/features/auth/keys";
import { dashboardKeys } from "@/features/dashboard/keys";
import { projectKeys } from "@/features/projects/keys";
import { taskKeys } from "@/features/tasks/keys";

const apiError = (status: number) => new ApiError({ status, code: "X", message: "m" });

describe("retry policy", () => {
  it.each([400, 401, 403, 404, 422, 429])("never retries a %i", (status) => {
    expect(shouldRetry(0, apiError(status))).toBe(false);
  });

  it("retries network failures and server errors twice", () => {
    for (const status of [0, 500, 503]) {
      expect(shouldRetry(0, apiError(status))).toBe(true);
      expect(shouldRetry(1, apiError(status))).toBe(true);
      expect(shouldRetry(2, apiError(status))).toBe(false);
    }
  });

  it("retries unknown errors a limited number of times", () => {
    expect(shouldRetry(0, new Error("x"))).toBe(true);
    expect(shouldRetry(2, new Error("x"))).toBe(false);
  });
});

describe("query client defaults", () => {
  it("does not retry mutations and does not refetch on focus", () => {
    const defaults = createQueryClient().getDefaultOptions();

    expect(defaults.mutations?.retry).toBe(false);
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
    expect(defaults.queries?.retry).toBe(shouldRetry);
  });
});

describe("query keys", () => {
  it("nest under one root per feature so a root can invalidate everything below it", () => {
    expect(projectKeys.list({ q: "a" }).slice(0, 1)).toEqual(projectKeys.all);
    expect(projectKeys.members("p1").slice(0, 2)).toEqual(projectKeys.details());
    expect(taskKeys.list("p1", { page: 2 }).slice(0, 2)).toEqual(taskKeys.lists());
    expect(authKeys.me()[0]).toBe(authKeys.all[0]);
    expect(dashboardKeys.stats()[0]).toBe(dashboardKeys.all[0]);
    expect(activityKeys.project("p1", {})[0]).toBe(activityKeys.all[0]);
  });

  it("differ when the parameters differ", () => {
    expect(taskKeys.list("p1", { page: 1 })).not.toEqual(taskKeys.list("p1", { page: 2 }));
    expect(taskKeys.list("p1", {})).not.toEqual(taskKeys.list("p2", {}));
    expect(projectKeys.detail("a")).not.toEqual(projectKeys.detail("b"));
  });
});
