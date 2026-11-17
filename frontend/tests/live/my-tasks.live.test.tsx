/**
 * The My Tasks page against the REAL backend (`GET /me/tasks`), with three real users: Ana owns
 * a project and adds Ben; Ben also owns a project of his own; Dan is an outsider with his own
 * project. Nothing is mocked except the Next.js router. Run with the backend up: pnpm test:live
 * It registers three throwaway users and three projects (deleted again at the end).
 */
import { configure, screen, within } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { as, person } from "./people";

vi.mock("@/config/env", () => ({
  publicEnv: {
    NEXT_PUBLIC_API_BASE_URL: process.env.LIVE_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "live",
  },
}));
vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

import { register } from "@/features/auth/api";
import { addMember, createProject, deleteProject, removeMember } from "@/features/projects/api";
import { changeTaskStatus, createTask, listMyTasks } from "@/features/tasks/api";
import { DEFAULT_MY_TASK_FILTERS, toMyTaskListParams } from "@/features/tasks/my-tasks-filters";
import { MyTasksView } from "@/features/tasks/my-tasks-view";
import { renderWithAuth, resetNav } from "../auth/utils";

configure({ asyncUtilTimeout: 8000 });

const stamp = Date.now();
const password = "live-test-password-1";
const ana = person("mytaskslive", "ana", "Ana Owner", stamp);
const ben = person("mytaskslive", "ben", "Ben Assignee", stamp);
const dan = person("mytaskslive", "dan", "Dan Outsider", stamp);
const id = (who: typeof ana) => who.user?.id ?? "";

let teamProject = "";
let benProject = "";
let danProject = "";
const tasks: Record<string, string> = {};

beforeAll(async () => {
  for (const who of [ana, ben, dan]) {
    as(who);
    who.user = await register({ name: who.name, email: who.email, password });
  }
  as(ana);
  teamProject = (await createProject({ name: "Live team project" })).id;
  await addMember(teamProject, { email: ben.email });
  tasks.team = (
    await createTask(teamProject, {
      title: "Team task for Ben",
      description: "From Ana",
      priority: "high",
      assignee_id: id(ben),
      due_date: "2000-01-01",
    })
  ).id;
  tasks.anas = (
    await createTask(teamProject, { title: "Ana keeps this", assignee_id: id(ana) })
  ).id;

  as(ben);
  benProject = (await createProject({ name: "Live Ben solo" })).id;
  tasks.solo = (await createTask(benProject, { title: "Solo task", assignee_id: id(ben) })).id;
  const finished = await createTask(benProject, {
    title: "Finished solo task",
    description: "Done already",
    priority: "low",
    assignee_id: id(ben),
    due_date: "2099-01-01",
  });
  tasks.finished = finished.id;
  await changeTaskStatus(finished.id, { status: "in_progress" });
  await changeTaskStatus(finished.id, { status: "completed" });

  as(dan);
  danProject = (await createProject({ name: "Live Dan only" })).id;
  await createTask(danProject, { title: "Dan's task", assignee_id: id(dan) });
});

afterAll(async () => {
  for (const [who, projectId] of [
    [ana, teamProject],
    [ben, benProject],
    [dan, danProject],
  ] as const) {
    if (!projectId) continue;
    as(who);
    await deleteProject(projectId).catch(() => undefined);
  }
  vi.unstubAllGlobals();
});

describe("GET /me/tasks against the real backend", () => {
  it("returns only my tasks, from every project I am in, each with its project", async () => {
    as(ben);
    const page = await listMyTasks({ sort: "due_date" });

    expect(page.data.map((task) => task.id).sort()).toEqual(
      [tasks.team, tasks.solo, tasks.finished].sort(),
    );
    expect(page.meta.total).toBe(3);
    const team = page.data.find((task) => task.id === tasks.team);
    expect(team?.project).toEqual({ id: teamProject, name: "Live team project", status: "active" });
    expect(team?.creator.id).toBe(id(ana));
    expect(team?.allowed_actions).toContain("update"); // Ben is the assignee
    expect(team?.allowed_actions).not.toContain("delete"); // only Ana (the owner) may delete
    const solo = page.data.find((task) => task.id === tasks.solo);
    expect(solo?.allowed_actions).toContain("delete"); // Ben owns that project
  });

  it("sends the page's default filters in a form the backend accepts: open tasks only", async () => {
    as(ben);
    const page = await listMyTasks(toMyTaskListParams(DEFAULT_MY_TASK_FILTERS));

    expect(page.data.map((task) => task.id).sort()).toEqual([tasks.team, tasks.solo].sort());
  });

  it("filters by project and overdue", async () => {
    as(ben);
    const solo = await listMyTasks({ project_id: benProject });
    const overdue = await listMyTasks({ overdue: true });

    expect(solo.data.map((task) => task.title).sort()).toEqual(["Finished solo task", "Solo task"]);
    expect(overdue.data.map((task) => task.id)).toEqual([tasks.team]);
  });

  it("never shows another person's project, even when asked for it by id", async () => {
    as(ben);
    expect((await listMyTasks({ project_id: danProject })).data).toEqual([]);
    as(dan);
    expect((await listMyTasks({})).data.map((task) => task.title)).toEqual(["Dan's task"]);
  });

  it("renders the page with the open tasks and their projects", async () => {
    as(ben);
    resetNav("/my-tasks");
    renderWithAuth(<MyTasksView />);

    const table = within(await screen.findByRole("table"));
    expect(await table.findByRole("link", { name: "Team task for Ben" })).toHaveAttribute(
      "href",
      `/projects/${teamProject}/tasks/${tasks.team}`,
    );
    expect(table.getByRole("link", { name: "Live Ben solo" })).toHaveAttribute(
      "href",
      `/projects/${benProject}`,
    );
    expect(table.queryByText("Finished solo task")).not.toBeInTheDocument();
    expect(screen.getByText("2 tasks assigned to you (open)")).toBeInTheDocument();
  });

  it("drops a project's tasks as soon as I am removed from it", async () => {
    as(ana);
    await removeMember(teamProject, id(ben));

    as(ben);
    const page = await listMyTasks({});
    expect(page.data.map((task) => task.id).sort()).toEqual([tasks.solo, tasks.finished].sort());
  });
});
