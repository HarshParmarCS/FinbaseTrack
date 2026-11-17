import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MyTasksView } from "@/features/tasks/my-tasks-view";
import {
  parseMyTaskFilters,
  toMyTaskListParams,
  toMyTaskSearchParams,
} from "@/features/tasks/my-tasks-filters";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { nav, renderWithAuth, resetNav } from "../auth/utils";
import { calls, failure, paged, project, route } from "../projects/fixtures";
import { ben, me, task, taskPage } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;
const LIST = "GET /api/v1/me/tasks";
const PROJECTS = "GET /api/v1/projects";
const PROJECT_ID = "11111111-1111-4111-8111-111111111111";

beforeEach(() => {
  resetNav("/my-tasks");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const website = { id: "p1", name: "Website redesign", status: "active" };
const archive = { id: "p2", name: "Old archive", status: "archived" };

const late = {
  ...task("t1", "Write copy", {
    priority: "high",
    due_date: "2000-01-01",
    assignee: me,
    creator: ben,
    description: "Landing page headline",
  }),
  project: website,
};
const archived = {
  ...task("t2", "Tidy files", {
    project_id: "p2",
    assignee: me,
    creator: me,
    due_date: null,
    allowed_actions: ["update", "delete"],
  }),
  project: archive,
};
const done = {
  ...task("t3", "Ship release", {
    status: "completed",
    assignee: me,
    completed_at: "2026-11-03T09:00:00Z",
    allowed_actions: [],
  }),
  project: website,
};

const standard = (tasks: object[] = [late, archived]) => ({
  [LIST]: () => reply(200, taskPage(tasks)),
  [PROJECTS]: () =>
    reply(200, paged([project("p1", "Website redesign"), project(PROJECT_ID, "Mobile app")])),
});

async function renderMyTasks() {
  const view = renderWithAuth(<MyTasksView />);
  await screen.findByRole("heading", { level: 1, name: "My Tasks" });
  return view;
}

const listUrl = () => String(calls(fetchMock, "GET", "/me/tasks").at(-1)?.[0]);
const table = () => within(screen.getByRole("table"));
const row = (name: string) => within(table().getByRole("row", { name: new RegExp(name) }));

describe("the list", () => {
  it("asks for my open tasks, soonest due first, 20 per page", async () => {
    route(fetchMock, standard());
    await renderMyTasks();
    await screen.findByRole("table");

    expect(listUrl()).toBe(
      "/api/v1/me/tasks?status=todo&status=in_progress&sort=due_date&page=1&page_size=20",
    );
    expect(screen.getByText("2 tasks assigned to you (open)")).toBeInTheDocument();
  });

  it("shows every detail of a task with its project", async () => {
    route(fetchMock, standard());
    await renderMyTasks();
    await screen.findByRole("table");

    const first = row("Write copy");
    expect(first.getByRole("link", { name: "Write copy" })).toHaveAttribute(
      "href",
      "/projects/p1/tasks/t1",
    );
    expect(first.getByText("Landing page headline")).toBeInTheDocument();
    expect(first.getByRole("link", { name: "Website redesign" })).toHaveAttribute(
      "href",
      "/projects/p1",
    );
    expect(first.getByLabelText("Status of Write copy")).toHaveValue("todo");
    expect(first.getByText("High")).toBeInTheDocument();
    expect(first.getByText("Jan 1")).toBeInTheDocument();
    expect(first.getByText(/days overdue/)).toBeInTheDocument();
    expect(first.getByText("Ben Carter")).toBeInTheDocument();
    expect(first.getByText("Nov 1, 2026")).toBeInTheDocument(); // created

    const second = row("Tidy files");
    expect(second.getByText("Archived")).toBeInTheDocument();
    expect(second.getByText("No due date")).toBeInTheDocument();
    expect(second.getByText("You")).toBeInTheDocument(); // I created it
  });

  it("shows when a completed task was finished", async () => {
    resetNav("/my-tasks", "?view=completed");
    route(fetchMock, standard([done]));
    await renderMyTasks();
    await screen.findByRole("table");

    expect(row("Ship release").getByText("Done Nov 3, 2026")).toBeInTheDocument();
  });

  it("also renders each task as a card for small screens", async () => {
    route(fetchMock, standard());
    await renderMyTasks();

    const cards = within(await screen.findByRole("list", { name: "My tasks" }));
    expect(cards.getAllByRole("article")).toHaveLength(2);
    expect(cards.getByRole("link", { name: "Write copy" })).toBeInTheDocument();
    expect(cards.getAllByText("Created by")).toHaveLength(2);
  });

  it("explains an empty list and points to the projects", async () => {
    route(fetchMock, standard([]));
    await renderMyTasks();

    expect(await screen.findByText("Nothing assigned to you")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your projects" })).toHaveAttribute(
      "href",
      "/projects",
    );
  });

  it("shows a skeleton, then an error with retry", async () => {
    let failing = true;
    route(fetchMock, {
      ...standard(),
      [LIST]: () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong on our side.")
          : reply(200, taskPage([late])),
    });
    const user = userEvent.setup();
    renderWithAuth(<MyTasksView />);

    expect(await screen.findByLabelText("Loading your tasks")).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });
});

describe("filters", () => {
  it("sends every filter in the URL to the backend, using its parameter names", async () => {
    resetNav(
      "/my-tasks",
      `?q=copy&view=completed&priority=high&project=${PROJECT_ID}&overdue=true&due_after=2026-01-01&due_before=2026-12-31&sort=-priority&page=2`,
    );
    route(fetchMock, standard());
    await renderMyTasks();
    await screen.findByRole("table");

    expect(listUrl()).toBe(
      `/api/v1/me/tasks?q=copy&status=completed&priority=high&project_id=${PROJECT_ID}&overdue=true&due_after=2026-01-01&due_before=2026-12-31&sort=-priority&page=2&page_size=20`,
    );
    expect(screen.getByRole("button", { name: "Completed" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await screen.findByRole("option", { name: "Mobile app" })).toBeInTheDocument();
    expect(screen.getByLabelText("Project")).toHaveValue(PROJECT_ID);
    expect(screen.getByLabelText("Overdue only")).toBeChecked();
  });

  it("puts each control's change in the URL and returns to page 1", async () => {
    resetNav("/my-tasks", "?page=3");
    route(fetchMock, standard());
    const user = userEvent.setup();
    await renderMyTasks();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "All" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/my-tasks?view=all");
    await user.click(screen.getByRole("button", { name: "High" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/my-tasks?priority=high");
    await user.selectOptions(screen.getByLabelText("Sort tasks"), "-updated_at");
    expect(nav.replace).toHaveBeenLastCalledWith("/my-tasks?sort=-updated_at");
    await screen.findByRole("option", { name: "Mobile app" });
    await user.selectOptions(screen.getByLabelText("Project"), PROJECT_ID);
    expect(nav.replace).toHaveBeenLastCalledWith(`/my-tasks?project=${PROJECT_ID}`);
  });

  it("does not offer board order, which means nothing across projects", async () => {
    route(fetchMock, standard());
    await renderMyTasks();

    const sorts = within(screen.getByLabelText("Sort tasks")).getAllByRole("option");
    expect(sorts.map((option) => option.textContent)).not.toContain("Board order");
  });

  it("explains an empty filtered result and clears the filters", async () => {
    resetNav("/my-tasks", "?view=completed&q=zzz");
    route(fetchMock, standard([]));
    const user = userEvent.setup();
    await renderMyTasks();

    expect(await screen.findByText("No tasks match")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
    expect(nav.replace).toHaveBeenLastCalledWith("/my-tasks");
  });
});

describe("row actions follow what the backend allows", () => {
  it("offers Edit and Delete only when the task lists update and delete", async () => {
    route(fetchMock, standard([late, archived, done]));
    resetNav("/my-tasks", "?view=all");
    const user = userEvent.setup();
    await renderMyTasks();
    await screen.findByRole("table");

    await user.click(table().getByRole("button", { name: "Actions for Tidy files" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(table().getByRole("button", { name: "Actions for Write copy" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(table().getByRole("button", { name: "Actions for Ship release" }));
    expect(await screen.findByRole("menuitem", { name: "Open task" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Open project" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("filter state", () => {
  it("drops invalid URL values instead of sending them", () => {
    const state = parseMyTaskFilters(
      new URLSearchParams("view=weird&priority=urgent&project=nope&sort=position&page=-1"),
    );

    expect(toMyTaskListParams(state)).toEqual({
      status: ["todo", "in_progress"],
      sort: "due_date",
      page: 1,
      page_size: 20,
    });
    expect(toMyTaskSearchParams(state).toString()).toBe("");
  });

  it("maps each view to the statuses the backend filters on", () => {
    const statusOf = (view: string) =>
      toMyTaskListParams(parseMyTaskFilters(new URLSearchParams(`view=${view}`))).status;

    expect(statusOf("todo")).toEqual(["todo"]);
    expect(statusOf("in_progress")).toEqual(["in_progress"]);
    expect(statusOf("completed")).toEqual(["completed"]);
    expect(statusOf("all")).toBeUndefined();
  });
});
