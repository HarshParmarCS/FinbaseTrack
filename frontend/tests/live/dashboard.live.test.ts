/**
 * Checks the dashboard's data against the REAL backend: the statistics, the per-project task
 * queries and the activity metadata the UI relies on. Run with the backend up: pnpm test:live
 * It creates a throwaway user and one project (deleted at the end) in the backend's database.
 */
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { CookieJar } from "./cookie-jar";

vi.mock("@/config/env", () => ({
  publicEnv: {
    NEXT_PUBLIC_API_BASE_URL: process.env.LIVE_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "live",
  },
}));

import { register } from "@/features/auth/api";
import { describeActivity, learnFromEntries } from "@/features/activity/describe";
import { getDashboardStats } from "@/features/dashboard/api";
import { distributionFrom } from "@/features/dashboard/distribution";
import { completionPercent, utcToday } from "@/features/dashboard/format";
import { sortByDueDate } from "@/features/dashboard/tasks";
import { createProject, deleteProject, listProjects } from "@/features/projects/api";
import { changeTaskStatus, createTask, listTasks } from "@/features/tasks/api";
import type { ProjectDetailOut, UserOut } from "@/types/api";

const jar = new CookieJar(process.env.LIVE_ORIGIN ?? "http://localhost:3000");
const today = utcToday(new Date());
let me: UserOut;
let project: ProjectDetailOut;
const titles: Record<string, string> = {};

beforeAll(() => {
  vi.stubGlobal("fetch", jar.fetch);
});

afterAll(async () => {
  if (project) await deleteProject(project.id).catch(() => undefined);
  vi.unstubAllGlobals();
});

describe("dashboard data against the real backend", () => {
  it("sets up a user, a project and four tasks", async () => {
    me = await register({
      name: "Dash Live",
      email: `dashlive-${Date.now()}@example.com`,
      password: "live-test-password-1",
    });
    project = await createProject({ name: "Live dashboard check" });
    const make = async (key: string, fields: Parameters<typeof createTask>[1]) => {
      const created = await createTask(project.id, fields);
      titles[key] = created.id;
      return created;
    };
    const a = await make("A", { title: "A open mine", assignee_id: me.id, due_date: "2099-01-02" });
    await make("B", { title: "B overdue mine", assignee_id: me.id, due_date: "2000-01-01" });
    await make("C", { title: "C open unassigned", due_date: "2099-03-01" });
    await make("D", {
      title: "D done",
      description: "finished",
      priority: "low",
      assignee_id: me.id,
      due_date: "2099-02-01",
      status: "completed",
    });
    await changeTaskStatus(a.id, { status: "in_progress" });

    expect(Object.keys(titles)).toHaveLength(4);
  });

  it("returns the statistics the cards display", async () => {
    const stats = await getDashboardStats();

    expect(stats).toMatchObject({
      total_projects: 1,
      active_projects: 1,
      total_tasks: 4,
      completed_tasks: 1,
      pending_tasks: 3,
      overdue_tasks: 1,
      assigned_to_me: 2,
    });
    expect(completionPercent(stats.completed_tasks, stats.total_tasks)).toBe(25);
  });

  it("has per-project counts that add up to the statistics (status distribution)", async () => {
    const page = await listProjects({ page_size: 100 });
    const distribution = distributionFrom(page);

    expect(distribution).toEqual({
      counts: { todo: 2, in_progress: 1, completed: 1 },
      total: 4,
    });
    expect(page.data[0].allowed_actions).toContain("create_task");
  });

  it("returns my open tasks, earliest due first, with the dashboard's filters", async () => {
    const page = await listTasks(project.id, {
      assignee_id: me.id,
      status: ["todo", "in_progress"],
      sort: "due_date",
      page_size: 10,
    });

    expect(page.data.map((t) => t.title)).toEqual(["B overdue mine", "A open mine"]);
    expect(sortByDueDate(page.data).map((t) => t.title)).toEqual(page.data.map((t) => t.title));
    expect(page.meta.total).toBe(2);
  });

  it("returns upcoming open tasks from today on, excluding the overdue and completed ones", async () => {
    const page = await listTasks(project.id, {
      status: ["todo", "in_progress"],
      due_after: today,
      sort: "due_date",
      page_size: 5,
    });

    expect(page.data.map((t) => t.title)).toEqual(["A open mine", "C open unassigned"]);
  });

  it("writes activity metadata the UI can name (task titles and status moves)", async () => {
    const { recent_activity: activity } = await getDashboardStats();
    const learned = learnFromEntries(activity);
    const lookups = {
      currentUserId: me.id,
      projects: new Map([[project.id, project.name]]),
      projectsComplete: true,
      ...learned,
    };
    const sentence = (entry: (typeof activity)[number]) => {
      const d = describeActivity(entry, lookups);
      return [d.actor, d.verb, d.subject?.label, d.detail].filter(Boolean).join(" ");
    };

    const created = activity
      .filter((a) => a.action === "task.created")
      .map(sentence)
      .sort();
    expect(created).toEqual([
      "You created the task A open mine",
      "You created the task B overdue mine",
      "You created the task C open unassigned",
      "You created the task D done",
    ]);
    // The status change has no title in its metadata; the title comes from the task's own
    // "created" entry in the same feed.
    const moved = activity.find((a) => a.action === "task.status_changed");
    expect(moved && sentence(moved)).toBe("You moved A open mine from To do to In progress");
    for (const entry of activity)
      expect(describeActivity(entry, lookups).verb).not.toBe("made a change");
  });
});
