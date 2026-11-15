/**
 * The Activity module against the REAL backend: real events made by three real users, rendered
 * through the real pages (jsdom). Nothing is mocked except the Next.js router.
 * Run with the backend up:  pnpm test:live
 * It registers three throwaway users and one project (deleted at the end).
 */
import { configure, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { as, failure, person } from "./people";

vi.mock("@/config/env", () => ({
  publicEnv: {
    NEXT_PUBLIC_API_BASE_URL: process.env.LIVE_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "live",
  },
}));
vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

import { getMyActivity, getProjectActivity } from "@/features/activity/api";
import { ActivityView } from "@/features/activity/activity-view";
import { register } from "@/features/auth/api";
import { ProjectDetailView } from "@/features/projects/project-detail-view";
import { addMember, createProject, deleteProject, removeMember } from "@/features/projects/api";
import { changeTaskStatus, createTask, deleteTask, updateTask } from "@/features/tasks/api";
import { renderWithAuth, resetNav } from "../auth/utils";

configure({ asyncUtilTimeout: 8000 });

const stamp = Date.now();
const password = "live-test-password-1";
const ana = person("actlive", "ana", "Ana Owner", stamp);
const ben = person("actlive", "ben", "Ben Member", stamp);
const cy = person("actlive", "cy", "Cy Outsider", stamp);
let projectId = "";
let taskId = "";

beforeAll(async () => {
  for (const who of [ana, ben, cy]) {
    as(who);
    who.user = await register({ name: who.name, email: who.email, password });
  }
  as(ana);
  projectId = (await createProject({ name: "Live activity" })).id;
  await addMember(projectId, { email: ben.email });
  const task = await createTask(projectId, {
    title: "Write copy",
    description: "Hero text",
    priority: "low",
    due_date: "2099-12-31",
    assignee_id: ben.user?.id,
  });
  taskId = task.id;
  await updateTask(taskId, { priority: "high" });
  as(ben);
  await changeTaskStatus(taskId, { status: "in_progress" });
  as(ana);
  const throwaway = await createTask(projectId, { title: "Throwaway" });
  await deleteTask(throwaway.id);
});

afterAll(async () => {
  if (projectId) {
    as(ana);
    await deleteProject(projectId).catch(() => undefined);
  }
  vi.unstubAllGlobals();
});

const lines = (scope: HTMLElement) =>
  within(scope)
    .getAllByRole("listitem")
    .map((li) => li.querySelector("p")?.textContent ?? "");

describe("activity in my projects (GET /dashboard/activity)", () => {
  it("is ordered newest first by the backend", async () => {
    as(ana);
    const feed = await getMyActivity({ page_size: 100 });
    const times = feed.data.map((entry) => entry.created_at);

    expect(times).toEqual([...times].sort().reverse());
    expect(feed.data.every((entry) => entry.project_id === projectId)).toBe(true); // no auth events
  });

  it("renders every real event as a sentence, in the backend's order, with links", async () => {
    as(ana);
    resetNav("/activity");
    renderWithAuth(<ActivityView />);

    const today = await screen.findByRole("region", { name: "Today" });
    // Creating a task with an assignee records one "created" event (no separate "assigned").
    expect(lines(today)).toEqual([
      "You deleted the task Throwaway in Live activity",
      "You created the task Throwaway in Live activity",
      "Ben Member moved Write copy from To do to In progress in Live activity",
      "You updated Write copy set the priority to High in Live activity",
      "You created the task Write copy in Live activity",
      "You added Ben Member to Live activity",
      "You created the project Live activity",
    ]);
    expect(within(today).getAllByRole("link", { name: "Write copy" })[0]).toHaveAttribute(
      "href",
      `/projects/${projectId}/tasks/${taskId}`,
    );
    expect(within(today).queryByRole("link", { name: "Throwaway" })).not.toBeInTheDocument(); // deleted
    expect(within(today).getAllByRole("link", { name: "Live activity" })[0]).toHaveAttribute(
      "href",
      `/projects/${projectId}`,
    );
    for (const time of today.querySelectorAll("time")) {
      expect(time.getAttribute("datetime")).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    }
  });

  it("shows the same events to the member, with 'You' moved to him", async () => {
    as(ben);
    resetNav("/activity");
    renderWithAuth(<ActivityView />);

    const today = await screen.findByRole("region", { name: "Today" });
    expect(lines(today)).toContain(
      "You moved Write copy from To do to In progress in Live activity",
    );
    expect(lines(today)).toContain("Ana Owner added you to Live activity");
  });

  it("is empty for an outsider, who also cannot read the project's timeline", async () => {
    as(cy);
    resetNav("/activity");
    renderWithAuth(<ActivityView />);

    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
    expect((await failure(getProjectActivity(projectId, {}))).status).toBe(404);
  });
});

describe("the project's own timeline (GET /projects/{id}/activity)", () => {
  it("appears on the project page without repeating the project name", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    renderWithAuth(<ProjectDetailView projectId={projectId} />);

    const card = (await screen.findByRole("heading", { level: 2, name: "Activity" })).closest(
      '[data-slot="card"]',
    ) as HTMLElement;
    const today = await within(card).findByRole("region", { name: "Today" });
    expect(lines(today)[0]).toBe("You deleted the task Throwaway");
    expect(lines(today)).toContain("Ben Member moved Write copy from To do to In progress");
    expect(lines(today).at(-1)).toBe("You created the project Live activity");
  });

  it("pages past 20 entries with Load more", async () => {
    as(ana);
    for (let index = 1; index <= 14; index += 1) {
      await updateTask(taskId, { title: `Write copy v${index}` });
    }
    const total = (await getProjectActivity(projectId, {})).meta.total;
    expect(total).toBeGreaterThan(20);

    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);
    expect(await screen.findByText(`Showing 20 of ${total}`)).toBeInTheDocument();
    // Older entries name the task by its newest title, which the newer entries revealed.
    expect(screen.getAllByText(/Write copy v14/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText(`Showing ${total} of ${total}`)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    const card = screen
      .getByRole("heading", { level: 2, name: "Activity" })
      .closest('[data-slot="card"]') as HTMLElement;
    const all = lines(card);
    expect(all).toHaveLength(total);
    expect(all.at(-1)).toBe("You created the project Live activity"); // the oldest entry is last
  });
});

describe("access follows membership", () => {
  it("a removed member loses the feed immediately", async () => {
    as(ana);
    await removeMember(projectId, ben.user?.id ?? "");

    as(ben);
    expect((await getMyActivity({})).meta.total).toBe(0);
    expect((await failure(getProjectActivity(projectId, {}))).status).toBe(404);
    // Removing a member and unassigning their task happen in one transaction. The backend
    // stamps both with the same time (PostgreSQL now()), so their order between themselves is
    // not defined; they are still the two newest entries.
    as(ana);
    const newest = (await getProjectActivity(projectId, {})).data.slice(0, 2);
    expect(newest.map((entry) => entry.action).sort()).toEqual([
      "member.removed",
      "task.unassigned",
    ]);
    expect(newest[0].created_at).toBe(newest[1].created_at);
  });
});
