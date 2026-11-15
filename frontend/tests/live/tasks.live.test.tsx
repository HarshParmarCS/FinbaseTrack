/**
 * The Tasks module against the REAL backend, through the real pages (rendered in jsdom) and four
 * real users: Ana (project owner), Ben (assignee), Cy (member) and Dan (outsider). Nothing is
 * mocked except the Next.js router. Run with the backend up:  pnpm test:live
 * It registers four throwaway users and one project (deleted again by the last test).
 */
import { configure, screen, waitFor, within } from "@testing-library/react";
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

import { register } from "@/features/auth/api";
import { addMember, createProject, deleteProject, removeMember } from "@/features/projects/api";
import {
  changeTaskStatus,
  createTask,
  deleteTask,
  getTask,
  listTasks,
  updateTask,
} from "@/features/tasks/api";
import { TaskDetailView } from "@/features/tasks/task-detail-view";
import { TasksView } from "@/features/tasks/tasks-view";
import { getActionErrorMessage, isPermissionDenied } from "@/lib/api/errors";
import { nav, renderWithAuth, resetNav } from "../auth/utils";

configure({ asyncUtilTimeout: 8000 });

const stamp = Date.now();
const password = "live-test-password-1";
const ana = person("tasklive", "ana", "Ana Owner", stamp);
const ben = person("tasklive", "ben", "Ben Assignee", stamp);
const cy = person("tasklive", "cy", "Cy Member", stamp);
const dan = person("tasklive", "dan", "Dan Outsider", stamp);
const id = (who: typeof ana) => who.user?.id ?? "";

let projectId = "";
let anaTask = ""; // created by Ana, assigned to Ben, fully filled in
let cyTask = ""; // created by Cy, unassigned, bare
const ids: Record<string, string> = {}; // tasks made for the filter tests

beforeAll(async () => {
  for (const who of [ana, ben, cy, dan]) {
    as(who);
    who.user = await register({ name: who.name, email: who.email, password });
  }
  as(ana);
  projectId = (await createProject({ name: "Live tasks check" })).id;
  await addMember(projectId, { email: ben.email });
  await addMember(projectId, { email: cy.email });
});

afterAll(async () => {
  if (projectId) {
    as(ana);
    await deleteProject(projectId).catch(() => undefined);
  }
  vi.unstubAllGlobals();
});

function renderTasks(search = "") {
  resetNav(`/projects/${projectId}/tasks`, search);
  return renderWithAuth(<TasksView projectId={projectId} />);
}

function renderDetail(taskId: string, forProject = projectId) {
  resetNav(`/projects/${forProject}/tasks/${taskId}`);
  return renderWithAuth(<TaskDetailView projectId={forProject} taskId={taskId} />);
}

async function rowFor(title: string) {
  return (await screen.findByRole("link", { name: title })).closest("tr") as HTMLElement;
}

describe("create (a project member may create a task)", () => {
  it("owner creates a fully described task for Ben through the dialog", async () => {
    as(ana);
    const user = userEvent.setup();
    renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    const assignees = within(within(dialog).getByLabelText("Assignee")).getAllByRole("option");
    expect(assignees.map((o) => o.textContent)).toEqual([
      "Unassigned",
      "Ana Owner",
      "Ben Assignee",
      "Cy Member",
    ]); // only project members; Dan is not offered
    await user.type(within(dialog).getByLabelText("Title"), "Write launch copy");
    await user.type(within(dialog).getByLabelText("Description"), "Hero text and call to action");
    await user.selectOptions(within(dialog).getByLabelText("Priority"), "high");
    await user.type(within(dialog).getByLabelText("Due date"), "2099-12-31");
    await user.selectOptions(within(dialog).getByLabelText("Assignee"), id(ben));
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    const row = await rowFor("Write launch copy");
    expect(within(row).getByText("Ben Assignee")).toBeInTheDocument();
    expect(within(row).getByText("High")).toBeInTheDocument();
    expect(within(row).getByLabelText("Status of Write launch copy")).toHaveValue("todo");
    const stored = (await listTasks(projectId, { q: "launch copy" })).data[0];
    anaTask = stored.id;
    expect(stored).toMatchObject({
      description: "Hero text and call to action",
      due_date: "2099-12-31",
    });
    expect(stored.creator.id).toBe(id(ana));
  });

  it("another member (Cy) can create a task too, with only a title", async () => {
    as(cy);
    const user = userEvent.setup();
    renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));
    expect(await within(dialog).findByText("Enter a title")).toBeInTheDocument(); // validated locally
    await user.type(within(dialog).getByLabelText("Title"), "Cy's own task");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    await rowFor("Cy's own task");
    cyTask = (await listTasks(projectId, { q: "Cy's own" })).data[0].id;
    expect((await getTask(cyTask)).creator.id).toBe(id(cy));
  });

  it("an outsider cannot create one, and does not even see the project", async () => {
    as(dan);

    expect((await failure(createTask(projectId, { title: "Sneaky" }))).status).toBe(404);
    renderTasks();
    expect(await screen.findByText("Project not found")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New task" })).not.toBeInTheDocument();
  });

  it("rejects an assignee who is not a member (the backend's 422)", async () => {
    as(ana);
    const error = await failure(
      createTask(projectId, { title: "Bad assignee", assignee_id: id(dan) }),
    );

    expect(error.status).toBe(422);
    expect(error.code).toBe("BUSINESS_RULE_VIOLATION");
    expect(error.message).toBe("The assignee must be a member of the project.");
  });
});

describe("update (only the creator or the assignee)", () => {
  it("Cy, a member who is neither, sees no way to change Ana's task, and the backend refuses", async () => {
    as(cy);
    const user = userEvent.setup();
    renderTasks();
    const anaRow = await rowFor("Write launch copy");
    expect(within(anaRow).getByLabelText("Status of Write launch copy")).toBeDisabled();
    await user.click(within(anaRow).getByRole("button", { name: "Actions for Write launch copy" }));
    expect(await screen.findByRole("menuitem", { name: "Open" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    const ownRow = await rowFor("Cy's own task");
    expect(within(ownRow).getByLabelText("Status of Cy's own task")).toBeEnabled();

    const denied = await failure(updateTask(anaTask, { title: "Hijacked" }));
    expect(denied.status).toBe(403);
    expect(isPermissionDenied(denied)).toBe(true);
    expect(getActionErrorMessage(denied)).toBe(
      "You do not have permission to do this. Only the task creator or the task assignee can update a task.",
    );
    const deniedStatus = await failure(changeTaskStatus(anaTask, { status: "in_progress" }));
    expect(deniedStatus.status).toBe(403);
    expect((await getTask(anaTask)).title).toBe("Write launch copy");
  });

  it("the project owner gains no update rights over somebody else's task", async () => {
    as(ana);

    const error = await failure(updateTask(cyTask, { title: "Owner override" }));

    expect(error.status).toBe(403);
    expect(isPermissionDenied(error)).toBe(true);
  });

  it("Ben, the assignee, edits Ana's task through the page", async () => {
    as(ben);
    const user = userEvent.setup();
    renderDetail(anaTask);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Write launch copy" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Description"));
    await user.type(within(dialog).getByLabelText("Description"), "Edited by the assignee");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Edited by the assignee")).toBeInTheDocument();
    expect((await getTask(anaTask)).description).toBe("Edited by the assignee");
  });

  it("Ana, the creator, can clear and set optional fields (null clears)", async () => {
    as(ana);

    const cleared = await updateTask(anaTask, { due_date: null, assignee_id: null });
    expect(cleared).toMatchObject({ due_date: null, assignee: null });
    const restored = await updateTask(anaTask, {
      due_date: "2099-12-31",
      assignee_id: id(ben),
      priority: "high",
    });
    expect(restored.assignee?.id).toBe(id(ben));
  });

  it("rejects status and position on the generic update (they have their own endpoint)", async () => {
    as(ana);

    const error = await failure(updateTask(anaTask, { status: "completed" } as never));

    expect(error.status).toBe(422);
    expect((await getTask(anaTask)).status).toBe("todo");
  });
});

describe("status and completion", () => {
  it("does not allow todo to jump straight to completed (422)", async () => {
    as(ana);
    const error = await failure(changeTaskStatus(anaTask, { status: "completed" }));

    expect(error.status).toBe(422);
    expect(error.code).toBe("BUSINESS_RULE_VIOLATION");
  });

  it("Cy moves a bare task forward, but the backend will not complete it, and the UI says it is unavailable", async () => {
    as(cy);
    const user = userEvent.setup();
    renderTasks();
    const select = (await within(await rowFor("Cy's own task")).findByLabelText(
      "Status of Cy's own task",
    )) as HTMLSelectElement;
    await user.selectOptions(select, "in_progress");
    await waitFor(() => expect(select).toHaveValue("in_progress"));

    const completed = within(select).getAllByRole("option") as HTMLOptionElement[];
    expect(completed.map((o) => o.textContent)).toContain("Completed (not available yet)");
    expect(completed.find((o) => o.value === "completed")?.disabled).toBe(true);
    const error = await failure(changeTaskStatus(cyTask, { status: "completed" }));
    expect(error.status).toBe(403);
    expect(isPermissionDenied(error)).toBe(true);
    expect(error.details[0].policy_id).toBe("task-complete");
    expect((await getTask(cyTask)).status).toBe("in_progress");
  });

  it("Ben completes Ana's complete task through the status selector", async () => {
    as(ben);
    const user = userEvent.setup();
    renderDetail(anaTask);
    const select = (await screen.findByLabelText(
      "Status of Write launch copy",
    )) as HTMLSelectElement;
    await user.selectOptions(select, "in_progress");
    await waitFor(() => expect(select).toHaveValue("in_progress"));
    await waitFor(() => {
      const option = within(select)
        .getAllByRole("option")
        .find((o) => (o as HTMLOptionElement).value === "completed");
      expect((option as HTMLOptionElement).disabled).toBe(false); // the backend now lists "complete"
    });
    await user.selectOptions(select, "completed");

    await waitFor(() => expect(select).toHaveValue("completed"));
    const done = await getTask(anaTask);
    expect(done.status).toBe("completed");
    expect(done.completed_at).not.toBeNull();
  });

  it("will not let a completed task lose what completion needs", async () => {
    as(ana);
    const error = await failure(updateTask(anaTask, { assignee_id: null }));

    expect(error.status).toBe(403);
    expect(error.details[0].policy_id).toBe("task-complete");
    expect((await getTask(anaTask)).assignee?.id).toBe(id(ben));
  });
});

describe("delete (project owner only, and only while todo)", () => {
  it("the owner cannot delete a completed task, and the UI does not offer it", async () => {
    as(ana);
    const user = userEvent.setup();
    renderTasks();
    const row = await rowFor("Write launch copy");
    await user.click(within(row).getByRole("button", { name: "Actions for Write launch copy" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();

    const error = await failure(deleteTask(anaTask));
    expect(error.status).toBe(403);
    expect(error.details[0].policy_id).toBe("task-delete");
  });

  it("a member who created a todo task still cannot delete it (not the owner)", async () => {
    as(cy);
    const task = await createTask(projectId, { title: "Cy throwaway" });

    const error = await failure(deleteTask(task.id));

    expect(error.status).toBe(403);
    expect(isPermissionDenied(error)).toBe(true);
    expect(task.allowed_actions).not.toContain("delete");
    as(ana);
    await deleteTask(task.id); // the owner can: it is todo
    expect((await failure(getTask(task.id))).status).toBe(404);
  });

  it("the owner cannot delete an in-progress task, but can once it is back to todo (through the UI)", async () => {
    as(ana);
    expect((await failure(deleteTask(cyTask))).status).toBe(403); // Cy's task is in_progress
    as(cy);
    await changeTaskStatus(cyTask, { status: "todo" });

    as(ana);
    const user = userEvent.setup();
    renderTasks();
    const row = await rowFor("Cy's own task");
    await user.click(within(row).getByRole("button", { name: "Actions for Cy's own task" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Delete “Cy's own task”?")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Delete task" }));

    // The dialog closes only once the DELETE has succeeded; the row can vanish earlier (filtered
    // out by a refetch already in flight), so the dialog is what proves the request finished.
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Cy's own task" })).not.toBeInTheDocument(),
    );
    expect((await failure(getTask(cyTask))).status).toBe(404);
  });
});

describe("search, filter, sort and pagination on real data", () => {
  it("creates tasks that differ in every filterable field", async () => {
    as(ana);
    const make = async (key: string, fields: Parameters<typeof createTask>[1]) => {
      ids[key] = (await createTask(projectId, fields)).id;
    };
    await make("overdue", {
      title: "Zeta overdue",
      priority: "high",
      due_date: "2000-01-01",
      assignee_id: id(cy),
    });
    await make("soon", { title: "Alpha soon", priority: "low", due_date: "2098-01-01" });
    await make("later", {
      title: "Mid later",
      priority: "medium",
      due_date: "2099-06-01",
      assignee_id: id(ben),
    });
    await make("undated", { title: "Omega undated", priority: "medium" });
    await changeTaskStatus(ids.later, { status: "in_progress" }).catch(() => undefined);

    expect(Object.keys(ids)).toHaveLength(4);
  });

  const titles = async (params: Parameters<typeof listTasks>[1]) =>
    (await listTasks(projectId, params)).data.map((t) => t.title);

  it("searches by text, case-insensitively, in titles and descriptions", async () => {
    as(ana);

    expect(await titles({ q: "ALPHA" })).toEqual(["Alpha soon"]);
    expect(await titles({ q: "launch copy" })).toEqual(["Write launch copy"]);
    expect(await titles({ q: "no-such-text" })).toEqual([]);
  });

  it("filters by status and priority, with repeated values", async () => {
    as(ana);

    expect(await titles({ status: ["completed"] })).toEqual(["Write launch copy"]);
    expect((await titles({ priority: ["high"] })).sort()).toEqual([
      "Write launch copy",
      "Zeta overdue",
    ]);
    expect((await titles({ priority: ["low", "medium"] })).sort()).toEqual([
      "Alpha soon",
      "Mid later",
      "Omega undated",
    ]);
    expect(await titles({ status: ["in_progress"], priority: ["medium"] })).toEqual(["Mid later"]);
  });

  it("filters by assignee, unassigned, overdue and due-date range", async () => {
    as(ana);

    expect(await titles({ assignee_id: id(cy) })).toEqual(["Zeta overdue"]);
    expect((await titles({ assignee_id: "unassigned" })).sort()).toEqual([
      "Alpha soon",
      "Omega undated",
    ]);
    expect(await titles({ overdue: true })).toEqual(["Zeta overdue"]);
    expect((await titles({ overdue: false })).includes("Zeta overdue")).toBe(false);
    expect(await titles({ due_after: "2098-06-01", due_before: "2099-12-30" })).toEqual([
      "Mid later",
    ]);
  });

  it("sorts by due date (undated last), priority and title-independent fields", async () => {
    as(ana);

    expect(await titles({ sort: "due_date" })).toEqual([
      "Zeta overdue",
      "Alpha soon",
      "Mid later",
      "Write launch copy",
      "Omega undated",
    ]);
    expect((await titles({ sort: "-due_date" })).slice(0, 2)).toEqual([
      "Write launch copy",
      "Mid later",
    ]);
    const byPriority = await listTasks(projectId, { sort: "-priority" });
    const rank = { low: 1, medium: 2, high: 3 } as const;
    const ranks = byPriority.data.map((t) => rank[t.priority]);
    expect(ranks).toEqual([...ranks].sort((a, b) => b - a));
  });

  it("paginates with the backend's meta", async () => {
    as(ana);
    const first = await listTasks(projectId, { page_size: 2, sort: "due_date" });
    const last = await listTasks(projectId, { page_size: 2, page: 3, sort: "due_date" });

    expect(first.meta).toEqual({ page: 1, page_size: 2, total: 5, total_pages: 3 });
    expect(first.data).toHaveLength(2);
    expect(last.data).toHaveLength(1);
  });

  it("the page applies the URL's filters and shows only matching rows", async () => {
    as(ana);
    renderTasks("?priority=high&status=todo&sort=due_date");

    expect(await screen.findByRole("link", { name: "Zeta overdue" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Alpha soon" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Write launch copy" })).not.toBeInTheDocument(); // completed
    const row = await rowFor("Zeta overdue");
    expect(within(row).getByText(/\d+ days overdue/)).toBeInTheDocument();
    expect(screen.getByText("1 task match in Live tasks check")).toBeInTheDocument();
  });

  it("the page's controls change the URL", async () => {
    as(ana);
    const user = userEvent.setup();
    renderTasks();
    await screen.findByRole("link", { name: "Zeta overdue" });

    await user.click(screen.getByRole("button", { name: "Completed" }));
    expect(nav.replace).toHaveBeenLastCalledWith(`/projects/${projectId}/tasks?status=completed`);
  });
});

describe("visibility and access", () => {
  it("Dan, an outsider, gets 'not found' for the task page and for the same task under another project", async () => {
    as(dan);
    renderDetail(anaTask);

    expect(await screen.findByText("Task not found")).toBeInTheDocument();
    expect((await failure(getTask(anaTask))).status).toBe(404);
  });

  it("a member sees the task only under its own project", async () => {
    as(ben);
    renderDetail(anaTask, "00000000-0000-4000-8000-0000000000aa");

    expect(
      await screen.findByText("This task does not belong to this project."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 1, name: "Write launch copy" }),
    ).not.toBeInTheDocument();
  });

  it("removing a member unassigns their tasks in the same step and cuts their access", async () => {
    as(ana);
    expect((await getTask(ids.overdue)).assignee?.id).toBe(id(cy));

    await removeMember(projectId, id(cy));

    expect((await getTask(ids.overdue)).assignee).toBeNull();
    as(cy);
    expect((await failure(getTask(anaTask))).status).toBe(404);
    expect((await failure(listTasks(projectId, {}))).status).toBe(404);
    expect((await failure(createTask(projectId, { title: "Still here?" }))).status).toBe(404);
  });

  it("deletes the project and its tasks", async () => {
    as(ana);
    await deleteProject(projectId);

    expect((await failure(getTask(anaTask))).status).toBe(404);
    projectId = "";
  });
});
