import { describe, expect, it } from "vitest";
import {
  dayLabel,
  describeActivity,
  groupByDay,
  learnFromEntries,
  type Described,
  type Lookups,
} from "@/features/activity/describe";
import type { ActivityOut } from "@/types/api";

const ana = { id: "u1", email: "ana@example.com", name: "Ana Lopez" };
const ben = { id: "u2", email: "ben@example.com", name: "Ben Carter" };

function entry(
  action: ActivityOut["action"],
  metadata: Record<string, unknown> = {},
  extra: Partial<ActivityOut> = {},
): ActivityOut {
  return {
    id: `a-${action}`,
    user: ben,
    project_id: "p1",
    task_id: action.startsWith("task.") ? "t1" : null,
    action,
    metadata,
    created_at: "2026-11-15T10:00:00Z",
    ...extra,
  };
}

const lookups = (overrides: Partial<Lookups> = {}): Lookups => ({
  currentUserId: "u1",
  projects: new Map([["p1", "Website"]]),
  projectsComplete: true,
  people: new Map([
    ["u1", "Ana Lopez"],
    ["u2", "Ben Carter"],
    ["u3", "Cy Dunn"],
  ]),
  taskTitles: new Map(),
  deletedTasks: new Set(),
  ...overrides,
});

/** The sentence a reader sees, without markup. */
function sentence(d: Described, withProject = true): string {
  return [
    d.actor,
    d.verb,
    d.subject?.label,
    d.detail,
    withProject && d.project ? `in ${d.project.label}` : undefined,
  ]
    .filter(Boolean)
    .join(" ");
}

const say = (e: ActivityOut, l = lookups()) => sentence(describeActivity(e, l));

describe("actor", () => {
  it("is 'You' for the signed-in user and the name for anyone else", () => {
    expect(
      describeActivity(entry("project.created", { name: "Website" }, { user: ana }), lookups()),
    ).toMatchObject({
      actor: "You",
      isYou: true,
    });
    expect(describeActivity(entry("project.created"), lookups())).toMatchObject({
      actor: "Ben Carter",
      isYou: false,
    });
  });
});

describe("project events", () => {
  it("created, linked to the project", () => {
    const d = describeActivity(entry("project.created", { name: "Website" }), lookups());

    expect(sentence(d)).toBe("Ben Carter created the project Website");
    expect(d.subject?.href).toBe("/projects/p1");
  });

  it("updated, listing what changed with the backend's values", () => {
    const e = entry("project.updated", {
      changes: {
        name: ["Old", "Website v2"],
        status: ["active", "archived"],
        description: ["a", "b"],
      },
    });

    expect(say(e)).toBe(
      "Ben Carter updated the project Website renamed it to “Website v2”, set the status to Archived and changed the description",
    );
  });

  it("deleted, named from the metadata and never linked", () => {
    const d = describeActivity(
      entry(
        "project.deleted",
        { name: "Gone", member_count: 2, task_count: 3 },
        { project_id: "p9" },
      ),
      lookups(),
    );

    expect(sentence(d)).toBe("Ben Carter deleted the project Gone");
    expect(d.subject?.href).toBeUndefined();
  });

  it("falls back honestly for a project the user can no longer open", () => {
    const d = describeActivity(entry("project.created", {}, { project_id: "p9" }), lookups());

    expect(d.subject).toEqual({ label: "a project you can no longer open" });
  });

  it("does not claim that when it only has part of the project list", () => {
    const partial = lookups({ projectsComplete: false });

    expect(
      describeActivity(entry("project.created", {}, { project_id: "p9" }), partial).subject,
    ).toEqual({
      label: "a project",
    });
    expect(
      describeActivity(entry("project.deleted", { name: "Gone" }, { project_id: "p9" }), partial)
        .subject,
    ).toEqual({
      label: "Gone",
    });
  });
});

describe("member events", () => {
  it("names a known member, and 'you' for the signed-in user", () => {
    expect(say(entry("member.added", { member_user_id: "u3" }))).toBe(
      "Ben Carter added Cy Dunn to Website",
    );
    expect(say(entry("member.added", { member_user_id: "u1" }))).toBe(
      "Ben Carter added you to Website",
    );
  });

  it("says 'a former member' when the removed person's name is unknown, with the unassign count", () => {
    expect(say(entry("member.removed", { member_user_id: "u9", unassigned_task_count: 2 }))).toBe(
      "Ben Carter removed a former member from Website (2 tasks unassigned)",
    );
    expect(say(entry("member.removed", { member_user_id: "u3", unassigned_task_count: 1 }))).toBe(
      "Ben Carter removed Cy Dunn from Website (1 task unassigned)",
    );
    expect(say(entry("member.removed", { member_user_id: "u3", unassigned_task_count: 0 }))).toBe(
      "Ben Carter removed Cy Dunn from Website",
    );
  });
});

describe("task events", () => {
  it("created, with the title from the metadata and a link to the task", () => {
    const d = describeActivity(
      entry("task.created", { title: "Write copy", status: "todo" }),
      lookups(),
    );

    expect(sentence(d)).toBe("Ben Carter created the task Write copy in Website");
    expect(d.subject?.href).toBe("/projects/p1/tasks/t1");
    expect(d.project?.href).toBe("/projects/p1");
  });

  it("updated, listing the changed fields with readable values", () => {
    const e = entry("task.updated", {
      changes: {
        title: ["Old", "New title"],
        priority: ["low", "high"],
        due_date: ["2026-01-01", "2026-03-01"],
        description: [null, "x"],
      },
    });

    expect(say(e)).toBe(
      "Ben Carter updated New title changed the title, set the priority to High, set the due date to Mar 1 and changed the description in Website",
    );
    expect(say(entry("task.updated", { changes: { due_date: ["2026-01-01", null] } }))).toBe(
      "Ben Carter updated a task removed the due date in Website",
    );
  });

  it("moved, with readable statuses, and a reorder within one column", () => {
    expect(
      say(entry("task.status_changed", { from: "todo", to: "in_progress", position: 1 })),
    ).toBe("Ben Carter moved a task from To do to In progress in Website");
    expect(say(entry("task.status_changed", { from: "todo", to: "todo", position: 3 }))).toBe(
      "Ben Carter moved a task within To do in Website",
    );
  });

  it("takes a title it does not have in the metadata from what the feed already revealed", () => {
    const l = lookups({ taskTitles: new Map([["t1", "Write copy"]]) });

    expect(say(entry("task.status_changed", { from: "in_progress", to: "completed" }), l)).toBe(
      "Ben Carter moved Write copy from In progress to Completed in Website",
    );
  });

  it("assigned and unassigned, naming the people involved", () => {
    expect(say(entry("task.assigned", { assignee_id: "u3", previous_assignee_id: null }))).toBe(
      "Ben Carter assigned a task to Cy Dunn in Website",
    );
    expect(say(entry("task.assigned", { assignee_id: "u1" }))).toBe(
      "Ben Carter assigned a task to you in Website",
    );
    expect(say(entry("task.unassigned", { previous_assignee_id: "u3" }))).toBe(
      "Ben Carter unassigned a task in Website",
    );
    expect(
      say(entry("task.unassigned", { reason: "member_removed", former_assignee_id: "u3" })),
    ).toBe("Ben Carter unassigned a task because the assignee left the project in Website");
  });

  it("deleted: named from the metadata and not linked, and other entries for it lose their link", () => {
    const deleted = describeActivity(
      entry("task.deleted", { title: "Throwaway", status: "todo" }),
      lookups(),
    );
    expect(sentence(deleted)).toBe("Ben Carter deleted the task Throwaway in Website");
    expect(deleted.subject?.href).toBeUndefined();

    const earlier = describeActivity(
      entry("task.created", { title: "Throwaway" }),
      lookups({ deletedTasks: new Set(["t1"]) }),
    );
    expect(earlier.subject?.href).toBeUndefined();
  });

  it("does not link a task in a project the user can no longer open", () => {
    const d = describeActivity(
      entry("task.created", { title: "X" }, { project_id: "p9" }),
      lookups(),
    );

    expect(d.subject?.href).toBeUndefined();
  });
});

describe("robustness", () => {
  it("ignores metadata of the wrong shape instead of showing it", () => {
    expect(say(entry("task.created", { title: 42 }))).toBe(
      "Ben Carter created the task a task in Website",
    );
    expect(say(entry("task.updated", { changes: "nope" }))).toBe(
      "Ben Carter updated a task in Website",
    );
    expect(say(entry("member.removed", { member_user_id: 7, unassigned_task_count: "2" }))).toBe(
      "Ben Carter removed a former member from Website",
    );
  });

  it("has a sentence for every action the backend writes", () => {
    const actions: ActivityOut["action"][] = [
      "user.registered",
      "auth.login",
      "auth.logout",
      "auth.refresh_reuse_detected",
      "project.created",
      "project.updated",
      "project.deleted",
      "member.added",
      "member.removed",
      "task.created",
      "task.updated",
      "task.status_changed",
      "task.assigned",
      "task.unassigned",
      "task.deleted",
    ];
    for (const action of actions)
      expect(describeActivity(entry(action), lookups()).verb).not.toBe("made a change");
  });
});

describe("learnFromEntries", () => {
  it("collects actors, the latest known title per task, and deleted tasks", () => {
    const learned = learnFromEntries([
      entry("task.updated", { changes: { title: ["Old", "Newest"] } }, { id: "3" }),
      entry("task.created", { title: "Old" }, { id: "2", user: ana }),
      entry("task.deleted", { title: "Gone" }, { id: "1", task_id: "t2" }),
    ]);

    expect(learned.taskTitles.get("t1")).toBe("Newest");
    expect(learned.taskTitles.get("t2")).toBe("Gone");
    expect(learned.deletedTasks).toEqual(new Set(["t2"]));
    expect(learned.people).toEqual(
      new Map([
        ["u2", "Ben Carter"],
        ["u1", "Ana Lopez"],
      ]),
    );
  });
});

describe("days", () => {
  const now = new Date(2026, 10, 15, 18, 0);
  const at = (y: number, m: number, d: number, h = 12) => new Date(y, m, d, h).toISOString();

  it("labels today, yesterday, older dates, and other years", () => {
    expect(dayLabel(at(2026, 10, 15, 1), now)).toBe("Today");
    expect(dayLabel(at(2026, 10, 14, 23), now)).toBe("Yesterday");
    expect(dayLabel(at(2026, 10, 10), now)).toBe("Tue, Nov 10");
    expect(dayLabel(at(2025, 11, 31), now)).toBe("Wed, Dec 31, 2025");
  });

  it("groups by day in the backend's order and drops entries repeated across pages", () => {
    const e = (id: string, iso: string) => entry("task.created", {}, { id, created_at: iso });
    const groups = groupByDay(
      [
        e("4", at(2026, 10, 15, 16)),
        e("3", at(2026, 10, 15, 9)),
        e("2", at(2026, 10, 14)),
        e("2", at(2026, 10, 14)),
        e("1", at(2026, 10, 10)),
      ],
      now,
    );

    expect(groups.map((g) => [g.label, g.entries.map((x) => x.id)])).toEqual([
      ["Today", ["4", "3"]],
      ["Yesterday", ["2"]],
      ["Tue, Nov 10", ["1"]],
    ]);
  });
});

describe("timeline dot kinds", () => {
  it("groups actions into families for the dot color", async () => {
    const { eventKind } = await import("@/features/activity/activity-timeline");

    expect(eventKind("project.created")).toBe("project");
    expect(eventKind("project.deleted")).toBe("removal");
    expect(eventKind("member.added")).toBe("member");
    expect(eventKind("member.removed")).toBe("removal");
    expect(eventKind("task.status_changed")).toBe("task");
    expect(eventKind("task.deleted")).toBe("removal");
    expect(eventKind("auth.login")).toBe("account");
  });
});
