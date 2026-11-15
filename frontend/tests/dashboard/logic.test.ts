import { describe, expect, it } from "vitest";
import { distributionFrom } from "@/features/dashboard/distribution";
import {
  completionPercent,
  daysUntil,
  describeDue,
  firstName,
  formatDueDate,
  greetingFor,
  relativeTime,
  utcToday,
} from "@/features/dashboard/format";
import { isOverdue, sortByDueDate } from "@/features/dashboard/tasks";
import type { PagedEnvelope, ProjectOut, TaskOut } from "@/types/api";

const user = { id: "u1", email: "a@b.co", name: "Ana" };

function task(overrides: Partial<TaskOut>): TaskOut {
  return {
    id: "t",
    project_id: "p",
    title: "Task",
    description: null,
    status: "todo",
    priority: "medium",
    assignee: null,
    creator: user,
    due_date: null,
    position: 1,
    completed_at: null,
    allowed_actions: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function project(id: string, counts: [number, number, number]): ProjectOut {
  return {
    id,
    name: id,
    description: null,
    status: "active",
    owner: user,
    member_count: 1,
    task_counts: { todo: counts[0], in_progress: counts[1], completed: counts[2] },
    allowed_actions: [],
    created_at: "x",
    updated_at: "x",
  };
}

describe("greeting and dates", () => {
  it.each([
    [0, "Good morning"],
    [11, "Good morning"],
    [12, "Good afternoon"],
    [17, "Good afternoon"],
    [18, "Good evening"],
    [23, "Good evening"],
  ])("hour %i is %s", (hour, expected) => {
    expect(greetingFor(hour)).toBe(expected);
  });

  it("uses the first name", () => {
    expect(firstName("  Ana Maria Lopez ")).toBe("Ana");
    expect(firstName("Ana")).toBe("Ana");
  });

  it("takes today from the UTC date, like the backend's overdue rule", () => {
    expect(utcToday(new Date("2026-11-15T23:30:00Z"))).toBe("2026-11-15");
    expect(utcToday(new Date("2026-11-16T00:30:00Z"))).toBe("2026-11-16");
  });

  it("formats a calendar date without a timezone shift", () => {
    expect(formatDueDate("2026-03-01")).toBe("Mar 1");
  });

  it("counts days between calendar dates", () => {
    expect(daysUntil("2026-11-20", "2026-11-15")).toBe(5);
    expect(daysUntil("2026-11-14", "2026-11-15")).toBe(-1);
    expect(daysUntil("2027-01-01", "2026-12-31")).toBe(1);
  });

  it.each([
    ["2026-11-15", "Due today"],
    ["2026-11-16", "Due tomorrow"],
    ["2026-11-20", "Due in 5 days"],
    ["2026-11-14", "1 day overdue"],
    ["2026-11-10", "5 days overdue"],
  ])("describes %s as %s", (due, expected) => {
    expect(describeDue(due, "2026-11-15")).toBe(expected);
  });

  it("describes relative times", () => {
    const now = new Date("2026-11-15T12:00:00Z");

    expect(relativeTime("2026-11-15T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-11-15T11:15:00Z", now)).toBe("45 minutes ago");
    expect(relativeTime("2026-11-15T09:00:00Z", now)).toBe("3 hours ago");
    expect(relativeTime("2026-11-13T12:00:00Z", now)).toBe("2 days ago");
  });
});

describe("completionPercent", () => {
  it("rounds to a whole percent", () => {
    expect(completionPercent(5, 8)).toBe(63);
    expect(completionPercent(0, 4)).toBe(0);
    expect(completionPercent(4, 4)).toBe(100);
  });

  it("is null, not 0 or NaN, when there are no tasks", () => {
    expect(completionPercent(0, 0)).toBeNull();
  });
});

describe("sortByDueDate and isOverdue", () => {
  it("orders by due date with undated tasks last, then by title", () => {
    const sorted = sortByDueDate([
      task({ id: "1", title: "No date", due_date: null }),
      task({ id: "2", title: "Later", due_date: "2026-12-01" }),
      task({ id: "3", title: "B same day", due_date: "2026-11-20" }),
      task({ id: "4", title: "A same day", due_date: "2026-11-20" }),
    ]);

    expect(sorted.map((t) => t.id)).toEqual(["4", "3", "2", "1"]);
  });

  it("does not mutate its input", () => {
    const input = [
      task({ id: "1", due_date: "2026-12-01" }),
      task({ id: "2", due_date: "2026-11-01" }),
    ];
    sortByDueDate(input);
    expect(input.map((t) => t.id)).toEqual(["1", "2"]);
  });

  it("is overdue only when past due and not completed", () => {
    expect(isOverdue(task({ due_date: "2026-11-14" }), "2026-11-15")).toBe(true);
    expect(isOverdue(task({ due_date: "2026-11-15" }), "2026-11-15")).toBe(false);
    expect(isOverdue(task({ due_date: "2026-11-01", status: "completed" }), "2026-11-15")).toBe(
      false,
    );
    expect(isOverdue(task({ due_date: null }), "2026-11-15")).toBe(false);
  });
});

describe("distributionFrom", () => {
  const page = (projects: ProjectOut[], total = projects.length): PagedEnvelope<ProjectOut> => ({
    data: projects,
    meta: { page: 1, page_size: 100, total, total_pages: 1 },
  });

  it("sums the counts of every project", () => {
    const result = distributionFrom(page([project("a", [1, 2, 3]), project("b", [4, 0, 1])]));

    expect(result).toEqual({ counts: { todo: 5, in_progress: 2, completed: 4 }, total: 11 });
  });

  it("is zero, not null, for projects without tasks", () => {
    expect(distributionFrom(page([project("a", [0, 0, 0])]))?.total).toBe(0);
  });

  it("refuses to present a partial total when not every project was loaded", () => {
    expect(distributionFrom(page([project("a", [1, 1, 1])], 150))).toBeNull();
  });
});
