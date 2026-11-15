import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TasksView } from "@/features/tasks/tasks-view";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { nav, renderWithAuth, resetNav } from "../auth/utils";
import { calls, csrfOf, detail, failure, member, route } from "../projects/fixtures";
import { ben, cy, me, task, taskPage } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;
const PROJECT = "GET /api/v1/projects/p1";
const LIST = "GET /api/v1/projects/p1/tasks";

beforeEach(() => {
  resetNav("/projects/p1/tasks");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const project = (extra: object = {}) =>
  detail("p1", "Website redesign", {
    members: [member(me, true), member(ben), member(cy)],
    ...extra,
  });

const mine = task("t1", "Write copy", { priority: "high", due_date: "2000-01-01", assignee: me });
const bens = task("t2", "Design page", { assignee: ben, allowed_actions: [] });
const loose = task("t3", "Plan sprint", {
  assignee: null,
  status: "in_progress",
  allowed_actions: ["update"],
});

const standard = (tasks = [mine, bens, loose]) => ({
  [PROJECT]: () => reply(200, { data: project() }),
  [LIST]: () => reply(200, taskPage(tasks)),
});

async function renderTasks() {
  const view = renderWithAuth(<TasksView projectId="p1" />);
  await screen.findByRole("heading", { level: 1, name: "Tasks" });
  return view;
}

const listUrl = () => String(calls(fetchMock, "GET", "/projects/p1/tasks")[0][0]);
const row = (name: string) => screen.getByRole("row", { name: new RegExp(name) });

describe("the table", () => {
  it("shows title, status, priority, assignee and due date for every task", async () => {
    route(fetchMock, standard());
    await renderTasks();

    expect(await screen.findByRole("link", { name: "Write copy" })).toHaveAttribute(
      "href",
      "/projects/p1/tasks/t1",
    );
    const first = row("Write copy");
    expect(within(first).getByLabelText("Status of Write copy")).toHaveValue("todo");
    expect(within(first).getByText("High")).toBeInTheDocument();
    expect(within(first).getByText("You")).toBeInTheDocument(); // assigned to me
    expect(within(first).getByText("Jan 1")).toBeInTheDocument();
    expect(within(first).getByText(/overdue/)).toBeInTheDocument(); // past due and not completed
    expect(within(row("Design page")).getByText("Ben Carter")).toBeInTheDocument();
    expect(within(row("Plan sprint")).getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("3 tasks in Website redesign")).toBeInTheDocument();
  });

  it("asks for 20 per page, newest first, with no filters", async () => {
    route(fetchMock, standard());
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    expect(listUrl()).toBe("/api/v1/projects/p1/tasks?sort=-created_at&page=1&page_size=20");
  });

  it("explains an empty project, and offers the first task only to someone who may create one", async () => {
    route(fetchMock, { ...standard([]) });
    await renderTasks();

    expect(await screen.findByText("No tasks yet")).toBeInTheDocument();
    expect(screen.getByText("Create the first task for this project.")).toBeInTheDocument();
  });

  it("does not offer task creation when the backend does not list create_task", async () => {
    route(fetchMock, {
      [PROJECT]: () => reply(200, { data: project({ allowed_actions: [] }) }),
      [LIST]: () => reply(200, taskPage([])),
    });
    await renderTasks();

    expect(
      await screen.findByText("Nobody has added a task to this project yet."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New task" })).not.toBeInTheDocument();
  });

  it("shows a skeleton, then an error with retry", async () => {
    let failing = true;
    route(fetchMock, {
      [PROJECT]: () => reply(200, { data: project() }),
      [LIST]: () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong on our side.")
          : reply(200, taskPage([mine])),
    });
    const user = userEvent.setup();
    renderWithAuth(<TasksView projectId="p1" />);

    expect(await screen.findByLabelText("Loading tasks")).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: "Write copy" })).toBeInTheDocument();
  });

  it("says so when the project is not found or the user is not in it", async () => {
    route(fetchMock, { [PROJECT]: () => failure(404, "NOT_FOUND", "Resource not found.") });
    renderWithAuth(<TasksView projectId="p1" />);

    expect(await screen.findByText("Project not found")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New task" })).not.toBeInTheDocument();
  });
});

describe("search, filter, sort and pagination", () => {
  it("sends every filter in the URL to the backend, using its parameter names", async () => {
    resetNav(
      "/projects/p1/tasks",
      "?q=login&status=todo&status=in_progress&priority=high&assignee=unassigned&overdue=true&due_after=2026-01-01&due_before=2026-12-31&sort=-priority&page=2",
    );
    route(fetchMock, {
      ...standard(),
      [LIST]: () => reply(200, taskPage([mine], { page: 2, total: 21, total_pages: 2 })),
    });
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    expect(listUrl()).toBe(
      "/api/v1/projects/p1/tasks?q=login&status=todo&status=in_progress&priority=high&assignee_id=unassigned&overdue=true&due_after=2026-01-01&due_before=2026-12-31&sort=-priority&page=2&page_size=20",
    );
    expect(screen.getByLabelText("Search tasks")).toHaveValue("login");
    expect(screen.getByRole("button", { name: "To do" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Completed" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByLabelText("Sort tasks")).toHaveValue("-priority");
    expect(screen.getByLabelText("Assignee")).toHaveValue("unassigned");
    expect(screen.getByLabelText("Overdue only")).toBeChecked();
  });

  it("puts each control's change in the URL and returns to page 1", async () => {
    resetNav("/projects/p1/tasks", "?page=3");
    route(fetchMock, standard());
    const user = userEvent.setup();
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    await user.click(screen.getByRole("button", { name: "In progress" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?status=in_progress");
    await user.click(screen.getByRole("button", { name: "High" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?priority=high");
    await user.selectOptions(screen.getByLabelText("Sort tasks"), "due_date");
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?sort=due_date");
    await user.selectOptions(screen.getByLabelText("Assignee"), "unassigned");
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?assignee=unassigned");
    await user.click(screen.getByLabelText("Overdue only"));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?overdue=true");
  });

  it("offers the project's members as assignee filters", async () => {
    route(fetchMock, standard());
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    const options = within(screen.getByLabelText("Assignee")).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "Anyone",
      "Unassigned",
      "Ana Lopez",
      "Ben Carter",
      "Cy Dunn",
    ]);
  });

  it("searches after the typing settles", async () => {
    route(fetchMock, standard());
    const user = userEvent.setup();
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    await user.type(screen.getByLabelText("Search tasks"), "copy");

    await waitFor(() => expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?q=copy"), {
      timeout: 2000,
    });
  });

  it("explains an empty result and clears the filters", async () => {
    resetNav("/projects/p1/tasks", "?status=completed&q=zzz");
    route(fetchMock, standard([]));
    const user = userEvent.setup();
    await renderTasks();

    expect(await screen.findByText("No tasks match")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks");
  });

  it("pages through results", async () => {
    route(fetchMock, {
      ...standard(),
      [LIST]: () => reply(200, taskPage([mine], { page: 1, total: 45, total_pages: 3 })),
    });
    const user = userEvent.setup();
    await renderTasks();

    expect(await screen.findByText("Page 1 of 3 · 45 in total")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects/p1/tasks?page=2");
  });
});

describe("row actions follow what the backend allows", () => {
  it("offers Edit and Delete only when the task lists update and delete", async () => {
    const deletable = task("t4", "Throwaway", { allowed_actions: ["update", "delete"] });
    route(fetchMock, standard([mine, bens, deletable]));
    const user = userEvent.setup();
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    await user.click(screen.getByRole("button", { name: "Actions for Throwaway" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("button", { name: "Actions for Write copy" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("button", { name: "Actions for Design page" }));
    expect(await screen.findByRole("menuitem", { name: "Open" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("status selector", () => {
  it("offers only the moves the backend accepts, and disables 'Completed' until it is available", async () => {
    const inProgress = task("t5", "Almost done", {
      status: "in_progress",
      allowed_actions: ["update"],
    });
    const ready = task("t6", "Ready", {
      status: "in_progress",
      allowed_actions: ["update", "complete"],
    });
    route(fetchMock, standard([mine, inProgress, ready]));
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    const optionsOf = (title: string) =>
      within(screen.getByLabelText(`Status of ${title}`)).getAllByRole(
        "option",
      ) as HTMLOptionElement[];
    expect(optionsOf("Write copy").map((o) => o.textContent)).toEqual(["To do", "In progress"]);
    const notReady = optionsOf("Almost done");
    expect(notReady.map((o) => o.textContent)).toEqual([
      "In progress",
      "To do",
      "Completed (not available yet)",
    ]);
    expect(notReady[2].disabled).toBe(true);
    expect(optionsOf("Ready")[2]).toHaveProperty("disabled", false);
  });

  it("is disabled for someone the backend does not allow to update the task", async () => {
    route(fetchMock, standard());
    await renderTasks();
    await screen.findByRole("link", { name: "Write copy" });

    expect(screen.getByLabelText("Status of Design page")).toBeDisabled();
    expect(screen.getByLabelText("Status of Write copy")).toBeEnabled();
  });

  it("changes the status through the status endpoint and refreshes the list", async () => {
    let sent: { body: unknown; csrf: string | null } | null = null;
    let status = "todo";
    route(fetchMock, {
      [PROJECT]: () => reply(200, { data: project() }),
      [LIST]: () => reply(200, taskPage([{ ...mine, status }])),
      "PATCH /api/v1/tasks/t1/status": (_u, init) => {
        sent = { body: JSON.parse(String(init?.body)), csrf: csrfOf(init) };
        status = "in_progress";
        return reply(200, { data: { ...mine, status } });
      },
    });
    const user = userEvent.setup();
    await renderTasks();
    await user.selectOptions(await screen.findByLabelText("Status of Write copy"), "in_progress");

    await waitFor(() =>
      expect(screen.getByLabelText("Status of Write copy")).toHaveValue("in_progress"),
    );
    expect(sent).toEqual({ body: { status: "in_progress" }, csrf: "tok" });
  });

  it("shows the backend's reason when it refuses, and keeps the old status", async () => {
    route(fetchMock, {
      ...standard([
        task("t5", "Almost done", {
          status: "in_progress",
          allowed_actions: ["update", "complete"],
        }),
      ]),
      "PATCH /api/v1/tasks/t5/status": () =>
        failure(
          403,
          "FORBIDDEN",
          "A task can be completed only when it has an assignee and its required fields are filled in.",
          "task-complete",
        ),
    });
    const user = userEvent.setup();
    await renderTasks();
    await user.selectOptions(await screen.findByLabelText("Status of Almost done"), "completed");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. A task can be completed only when it has an assignee",
    );
    expect(screen.getByLabelText("Status of Almost done")).toHaveValue("in_progress");
  });
});

describe("create task", () => {
  it("creates a task with every field and refreshes the list", async () => {
    let created: { url: string; body: unknown; csrf: string | null } | null = null;
    let listCalls = 0;
    route(fetchMock, {
      [PROJECT]: () => reply(200, { data: project() }),
      [LIST]: () => {
        listCalls += 1;
        return reply(200, taskPage([]));
      },
      "POST /api/v1/projects/p1/tasks": (url, init) => {
        created = { url: url.pathname, body: JSON.parse(String(init?.body)), csrf: csrfOf(init) };
        return reply(201, { data: task("t9", "Plan launch") });
      },
    });
    const user = userEvent.setup();
    await renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "  Plan launch  ");
    await user.type(within(dialog).getByLabelText("Description"), "Everything we need");
    await user.selectOptions(within(dialog).getByLabelText("Priority"), "high");
    await user.type(within(dialog).getByLabelText("Due date"), "2099-12-31");
    await user.selectOptions(within(dialog).getByLabelText("Assignee"), "u2");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(created).toEqual({
      url: "/api/v1/projects/p1/tasks",
      body: {
        title: "Plan launch",
        priority: "high",
        description: "Everything we need",
        assignee_id: "u2",
        due_date: "2099-12-31",
      },
      csrf: "tok",
    });
    await waitFor(() => expect(listCalls).toBe(2));
  });

  it("offers only project members as assignees", async () => {
    route(fetchMock, standard([]));
    const user = userEvent.setup();
    await renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);

    const options = within(
      await screen.findByLabelText("Assignee", { selector: "select#task-assignee" }),
    ).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "Unassigned",
      "Ana Lopez",
      "Ben Carter",
      "Cy Dunn",
    ]);
  });

  it("validates locally before sending", async () => {
    route(fetchMock, standard([]));
    const user = userEvent.setup();
    await renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    expect(await within(dialog).findByText("Enter a title")).toBeInTheDocument();
    expect(calls(fetchMock, "POST", "/tasks")).toHaveLength(0);
  });

  it("shows the backend's business-rule message inside the dialog", async () => {
    route(fetchMock, {
      ...standard([]),
      "POST /api/v1/projects/p1/tasks": () =>
        failure(422, "BUSINESS_RULE_VIOLATION", "The assignee must be a member of the project."),
    });
    const user = userEvent.setup();
    await renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "X");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "The assignee must be a member of the project.",
    );
  });

  it("shows a permission message when the backend refuses creation", async () => {
    route(fetchMock, {
      ...standard([]),
      "POST /api/v1/projects/p1/tasks": () =>
        failure(403, "FORBIDDEN", "Only project members can create tasks.", "task-create"),
    });
    const user = userEvent.setup();
    await renderTasks();
    await user.click((await screen.findAllByRole("button", { name: "New task" }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "X");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only project members can create tasks.",
    );
  });
});

describe("edit task", () => {
  async function openEdit(user: ReturnType<typeof userEvent.setup>, title: string) {
    await user.click(await screen.findByRole("button", { name: `Actions for ${title}` }));
    await user.click(await screen.findByRole("menuitem", { name: "Edit" }));
    return screen.findByRole("dialog");
  }

  it("starts from the task, sends only what changed, and clears fields with null", async () => {
    let patch: { url: string; body: unknown } | null = null;
    route(fetchMock, {
      ...standard([mine]),
      "PATCH /api/v1/tasks/t1": (url, init) => {
        patch = { url: url.pathname, body: JSON.parse(String(init?.body)) };
        return reply(200, { data: mine });
      },
    });
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openEdit(user, "Write copy");

    expect(within(dialog).getByLabelText("Title")).toHaveValue("Write copy");
    expect(within(dialog).getByLabelText("Priority")).toHaveValue("high");
    expect(within(dialog).getByLabelText("Assignee")).toHaveValue("u1");
    await user.selectOptions(within(dialog).getByLabelText("Priority"), "low");
    await user.selectOptions(within(dialog).getByLabelText("Assignee"), "");
    await user.clear(within(dialog).getByLabelText("Due date"));
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patch).toEqual({
      url: "/api/v1/tasks/t1",
      body: { priority: "low", assignee_id: null, due_date: null },
    });
    expect(JSON.stringify(patch)).not.toContain("status");
  });

  it("sends nothing when nothing changed", async () => {
    route(fetchMock, standard([mine]));
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openEdit(user, "Write copy");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls(fetchMock, "PATCH", "/tasks")).toHaveLength(0);
  });

  it("explains a denial even though the UI offered the button", async () => {
    route(fetchMock, {
      ...standard([mine]),
      "PATCH /api/v1/tasks/t1": () =>
        failure(
          403,
          "FORBIDDEN",
          "Only the task creator or the task assignee can update a task.",
          "task-update",
        ),
    });
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openEdit(user, "Write copy");
    await user.type(within(dialog).getByLabelText("Title"), " v2");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the task creator or the task assignee can update a task.",
    );
  });
});

describe("delete task", () => {
  const deletable = task("t4", "Throwaway", { allowed_actions: ["update", "delete"] });

  async function openDelete(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "Actions for Throwaway" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    return screen.findByRole("alertdialog");
  }

  it("asks first and sends nothing on cancel", async () => {
    route(fetchMock, standard([deletable]));
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openDelete(user);

    expect(within(dialog).getByText("Delete “Throwaway”?")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(calls(fetchMock, "DELETE", "/tasks")).toHaveLength(0);
  });

  it("deletes after confirmation and the task leaves the list", async () => {
    let remaining = [deletable];
    route(fetchMock, {
      [PROJECT]: () => reply(200, { data: project() }),
      [LIST]: () => reply(200, taskPage(remaining)),
      "DELETE /api/v1/tasks/t4": () => {
        remaining = [];
        return reply(204);
      },
    });
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openDelete(user);
    await user.click(within(dialog).getByRole("button", { name: "Delete task" }));

    expect(await screen.findByText("No tasks yet")).toBeInTheDocument();
  });

  it("shows the backend's reason when the delete is refused", async () => {
    route(fetchMock, {
      ...standard([deletable]),
      "DELETE /api/v1/tasks/t4": () =>
        failure(
          403,
          "FORBIDDEN",
          "Only the project owner can delete a task, and only while its status is todo.",
          "task-delete",
        ),
    });
    const user = userEvent.setup();
    await renderTasks();
    const dialog = await openDelete(user);
    await user.click(within(dialog).getByRole("button", { name: "Delete task" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the project owner can delete a task, and only while its status is todo.",
    );
  });
});
