import { describe, expect, it } from "vitest";
import {
  DEFAULT_SORT,
  hasActiveFilters,
  parseTaskFilters,
  toListParams,
  toSearchParams,
  toggle,
  type TaskFilterState,
} from "@/features/tasks/filters";
import { taskFormSchema } from "@/features/tasks/schemas";
import { NEXT_STATUSES, TASK_SORT_LABELS } from "@/features/tasks/status";
import { buildTaskCreate, buildTaskUpdate, formValuesFor } from "@/features/tasks/update";
import { TASK_SORTS, TASK_STATUSES, type TaskOut } from "@/types/api";

const USER = "11111111-1111-4111-8111-111111111111";
const parse = (query: string) => parseTaskFilters(new URLSearchParams(query));

describe("task filters in the URL", () => {
  it("defaults to a clean list", () => {
    expect(parse("")).toEqual({
      q: "",
      status: [],
      priority: [],
      assignee: "",
      overdue: false,
      dueAfter: "",
      dueBefore: "",
      sort: DEFAULT_SORT,
      page: 1,
    });
    expect(hasActiveFilters(parse(""))).toBe(false);
  });

  it("reads repeated status and priority keys, in the backend's order", () => {
    const state = parse("status=in_progress&status=todo&priority=high");

    expect(state.status).toEqual(["todo", "in_progress"]);
    expect(state.priority).toEqual(["high"]);
  });

  it("drops every invalid value instead of sending it to the backend", () => {
    const state = parse(
      "status=bogus&priority=urgent&assignee=someone&overdue=yes&due_after=2026-13-45&due_before=tomorrow&sort=title&page=0",
    );

    expect(state).toMatchObject({
      status: [],
      priority: [],
      assignee: "",
      overdue: false,
      dueAfter: "",
      dueBefore: "",
      sort: DEFAULT_SORT,
      page: 1,
    });
    expect(parse("page=abc").page).toBe(1);
    expect(parse("page=2.5").page).toBe(1);
  });

  it("accepts a user id or 'unassigned' as the assignee filter", () => {
    expect(parse(`assignee=${USER}`).assignee).toBe(USER);
    expect(parse("assignee=unassigned").assignee).toBe("unassigned");
  });

  it("limits the search text to the backend's 100 characters", () => {
    expect(parse(`q=${"x".repeat(150)}`).q).toHaveLength(100);
  });

  it("round-trips, leaving defaults out of the URL", () => {
    const state: TaskFilterState = {
      q: "login",
      status: ["todo", "completed"],
      priority: ["high"],
      assignee: "unassigned",
      overdue: true,
      dueAfter: "2026-01-01",
      dueBefore: "2026-12-31",
      sort: "-priority",
      page: 3,
    };

    const query = toSearchParams(state).toString();

    expect(query).toBe(
      "q=login&status=todo&status=completed&priority=high&assignee=unassigned&overdue=true&due_after=2026-01-01&due_before=2026-12-31&sort=-priority&page=3",
    );
    expect(parse(query)).toEqual(state);
    expect(toSearchParams(parse("")).toString()).toBe("");
  });

  it("builds the backend query: its parameter names, omitting what is not set", () => {
    const params = toListParams(parse(`status=todo&assignee=${USER}&overdue=true&page=2`), 20);

    expect(params).toEqual({
      q: undefined,
      status: ["todo"],
      priority: undefined,
      assignee_id: USER,
      overdue: true,
      due_after: undefined,
      due_before: undefined,
      sort: DEFAULT_SORT,
      page: 2,
      page_size: 20,
    });
  });

  it("toggles a value in a list without mutating it", () => {
    const list = ["todo"] as const;

    expect(toggle(list, "completed")).toEqual(["todo", "completed"]);
    expect(toggle(list, "todo")).toEqual([]);
    expect(list).toEqual(["todo"]);
  });

  it("has a label for every sort the backend supports", () => {
    expect(Object.keys(TASK_SORT_LABELS).sort()).toEqual([...TASK_SORTS].sort());
  });
});

describe("status moves", () => {
  it("follow the backend's line: todo <-> in_progress <-> completed", () => {
    expect(NEXT_STATUSES.todo).toEqual(["in_progress"]);
    expect([...NEXT_STATUSES.in_progress].sort()).toEqual(["completed", "todo"]);
    expect(NEXT_STATUSES.completed).toEqual(["in_progress"]);
    expect(Object.keys(NEXT_STATUSES).sort()).toEqual([...TASK_STATUSES].sort());
  });
});

describe("taskFormSchema", () => {
  const valid = {
    title: "Write copy",
    description: "",
    priority: "medium",
    assignee_id: "",
    due_date: "",
  };

  it("accepts the backend's limits and trims text", () => {
    expect(taskFormSchema.parse({ ...valid, title: "  Hi  " }).title).toBe("Hi");
    expect(
      taskFormSchema.safeParse({ ...valid, title: "t".repeat(200), description: "d".repeat(5000) })
        .success,
    ).toBe(true);
    expect(
      taskFormSchema.safeParse({ ...valid, due_date: "2026-02-28", assignee_id: USER }).success,
    ).toBe(true);
  });

  it.each([
    ["a blank title", { title: "   " }],
    ["a title over 200 characters", { title: "t".repeat(201) }],
    ["a description over 5000 characters", { description: "d".repeat(5001) }],
    ["an unknown priority", { priority: "urgent" }],
    ["a malformed date", { due_date: "15/11/2026" }],
    ["an impossible date", { due_date: "2026-02-30" }],
    ["a NUL character", { title: "bad\u0000title" }],
  ])("rejects %s", (_name, change) => {
    expect(taskFormSchema.safeParse({ ...valid, ...change }).success).toBe(false);
  });
});

function task(overrides: Partial<TaskOut> = {}): TaskOut {
  const user = { id: USER, email: "a@b.co", name: "Ana" };
  return {
    id: "t1",
    project_id: "p1",
    title: "Write copy",
    description: "Words",
    status: "todo",
    priority: "medium",
    assignee: user,
    creator: user,
    due_date: "2026-12-01",
    position: 1,
    completed_at: null,
    allowed_actions: ["update"],
    created_at: "x",
    updated_at: "x",
    ...overrides,
  };
}

describe("buildTaskCreate", () => {
  it("sends only what was filled in", () => {
    expect(
      buildTaskCreate({
        title: "A",
        description: "",
        priority: "low",
        assignee_id: "",
        due_date: "",
      }),
    ).toEqual({ title: "A", priority: "low" });
    expect(
      buildTaskCreate({
        title: "A",
        description: "d",
        priority: "high",
        assignee_id: USER,
        due_date: "2026-12-01",
      }),
    ).toEqual({
      title: "A",
      description: "d",
      priority: "high",
      assignee_id: USER,
      due_date: "2026-12-01",
    });
  });
});

describe("buildTaskUpdate", () => {
  const same = formValuesFor(task());

  it("is null when nothing changed", () => {
    expect(buildTaskUpdate(task(), same)).toBeNull();
  });

  it("sends only the changed fields and never status or position", () => {
    const update = buildTaskUpdate(task(), { ...same, title: "New", priority: "high" });

    expect(update).toEqual({ title: "New", priority: "high" });
    expect(update).not.toHaveProperty("status");
    expect(update).not.toHaveProperty("position");
  });

  it("clears optional fields with null (description, assignee, due date)", () => {
    expect(
      buildTaskUpdate(task(), { ...same, description: "", assignee_id: "", due_date: "" }),
    ).toEqual({
      description: null,
      assignee_id: null,
      due_date: null,
    });
  });

  it("treats missing and empty values as the same, and sets new ones", () => {
    const bare = task({ description: null, assignee: null, due_date: null });

    expect(buildTaskUpdate(bare, formValuesFor(bare))).toBeNull();
    expect(
      buildTaskUpdate(bare, {
        ...formValuesFor(bare),
        assignee_id: USER,
        due_date: "2027-01-01",
        description: "d",
      }),
    ).toEqual({ assignee_id: USER, due_date: "2027-01-01", description: "d" });
  });
});
