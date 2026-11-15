import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { utcToday } from "@/features/dashboard/format";
import {
  clearCookie,
  errorBody,
  reply,
  setCookie,
  stubFetch,
  type FetchMock,
} from "../api/helpers";
import { renderWithAuth, resetNav } from "../auth/utils";
import { me, paged, project, serve, stats, task, urls, type Backend } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

const NOW = new Date(2026, 10, 15, 9, 30); // local time, so the greeting is deterministic
let fetchMock: FetchMock;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetNav("/dashboard");
  setCookie("csrf_token", "t");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const projects = [
  project("p1", "Website redesign"),
  project("p2", "Old site", {
    status: "archived",
    member_count: 1,
    task_counts: { todo: 0, in_progress: 0, completed: 2 },
    allowed_actions: ["update"],
  }),
];

const healthy = (): Backend => ({
  stats: () => reply(200, { data: stats() }),
  projects: () => reply(200, paged(projects)),
  tasks: (url) => {
    const projectId = url.pathname.split("/")[4];
    return url.searchParams.has("assignee_id")
      ? reply(200, paged([task(`mine-${projectId}`, "Write copy")]))
      : reply(
          200,
          paged([
            task(`soon-${projectId}`, "Ship launch page", {
              due_date: "2099-02-01",
              assignee: null,
            }),
          ]),
        );
  },
});

async function renderDashboard() {
  const view = renderWithAuth(<DashboardView />);
  await screen.findByRole("heading", { level: 1 });
  return view;
}

describe("dashboard with data", () => {
  it("greets the user by first name with today's date", async () => {
    serve(fetchMock, healthy());
    renderWithAuth(<DashboardView />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Good morning, Ana" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Sunday, November 15, 2026")).toBeInTheDocument();
  });

  it("shows the statistics the backend returned, and the completion percentage", async () => {
    serve(fetchMock, healthy());
    await renderDashboard();

    const grid = await screen.findByRole("region", { name: "Statistics" });
    const value = (label: string) => within(grid).getByText(label).parentElement?.textContent;
    await waitFor(() => expect(value("Total tasks")).toContain("8"));
    expect(value("Total projects")).toContain("2");
    expect(value("Active projects")).toContain("1");
    expect(value("Completed")).toContain("5");
    expect(value("Pending")).toContain("3");
    expect(value("Overdue")).toContain("1");
    expect(value("Assigned to me")).toContain("2");
    expect(value("Completion")).toContain("63%"); // 5 of 8
  });

  it("lists my tasks, upcoming tasks, projects, status counts and activity", async () => {
    serve(fetchMock, healthy());
    await renderDashboard();

    expect(await screen.findByText("Write copy", { selector: "p.truncate" })).toBeInTheDocument();
    expect(await screen.findByText("Ship launch page")).toBeInTheDocument();
    expect(screen.getByText("2 assigned to you and not completed")).toBeInTheDocument();
    expect(screen.getByText("Old site")).toBeInTheDocument();
    expect(screen.getByText("Archived")).toBeInTheDocument();
    expect(screen.getByText("3 of 6 tasks done · 3 members")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "To do: 2, In progress: 1, Completed: 5" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Ben Carter")).toBeInTheDocument();
    expect(screen.getByText(/created a task/)).toBeInTheDocument();
  });

  it("asks the backend for exactly the tasks it needs, and only in projects with open work", async () => {
    serve(fetchMock, healthy());
    await renderDashboard();
    await screen.findByText("Ship launch page");

    const taskCalls = urls(fetchMock).filter((u) => u.includes("/tasks"));
    const mine = taskCalls.filter((u) => u.includes("assignee_id=u1"));
    const upcoming = taskCalls.filter((u) => u.includes("due_after="));
    expect(mine).toHaveLength(1);
    expect(mine[0]).toContain("/projects/p1/tasks");
    expect(mine[0]).toContain("status=todo&status=in_progress");
    expect(mine[0]).toContain("sort=due_date");
    expect(upcoming).toHaveLength(1);
    expect(upcoming[0]).toContain(`due_after=${utcToday(NOW)}`);
    expect(taskCalls.some((u) => u.includes("/projects/p2/"))).toBe(false); // nothing open there
  });
});

describe("dashboard empty states", () => {
  const empty: Backend = {
    stats: () =>
      reply(200, {
        data: stats({
          total_projects: 0,
          active_projects: 0,
          total_tasks: 0,
          completed_tasks: 0,
          pending_tasks: 0,
          overdue_tasks: 0,
          assigned_to_me: 0,
          recent_activity: [],
        }),
      }),
    projects: () => reply(200, paged([])),
    tasks: () => reply(200, paged([])),
  };

  it("explains each empty section and does not invent a completion percentage", async () => {
    serve(fetchMock, empty);
    await renderDashboard();

    expect(await screen.findByText("Nothing assigned to you")).toBeInTheDocument();
    expect(screen.getByText("No upcoming due dates")).toBeInTheDocument();
    expect(screen.getByText("No activity yet")).toBeInTheDocument();
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByText("No tasks yet", { selector: "h2" })).toBeInTheDocument();
    const grid = screen.getByRole("region", { name: "Statistics" });
    expect(within(grid).getByText("Completion").parentElement).toHaveTextContent("—");
    expect(within(grid).getByText("Completion").parentElement).toHaveTextContent("No tasks yet");
  });
});

describe("dashboard loading and errors", () => {
  it("shows skeletons while loading", async () => {
    fetchMock.mockImplementation(
      (input) =>
        new Promise((resolve) => {
          if (String(input).endsWith("/auth/me")) resolve(reply(200, { data: me }));
        }),
    );
    renderWithAuth(<DashboardView />);

    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByLabelText("Loading").length).toBeGreaterThan(0);
  });

  it("shows an error with retry for the statistics while other sections still work", async () => {
    let failing = true;
    serve(fetchMock, {
      ...healthy(),
      stats: () =>
        failing ? reply(500, errorBody("INTERNAL_ERROR", "boom")) : reply(200, { data: stats() }),
    });
    const user = userEvent.setup();
    await renderDashboard();

    expect(await screen.findByText("The statistics could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Old site")).toBeInTheDocument(); // projects are independent

    failing = false;
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]);

    const grid = await screen.findByRole("region", { name: "Statistics" });
    await waitFor(() =>
      expect(within(grid).getByText("Total tasks").parentElement).toHaveTextContent("8"),
    );
  });

  it("shows an error for the task lists when a project's tasks fail, and retries", async () => {
    let failing = true;
    serve(fetchMock, {
      ...healthy(),
      tasks: (url) =>
        failing
          ? reply(500, errorBody("INTERNAL_ERROR", "boom"))
          : url.searchParams.has("assignee_id")
            ? reply(200, paged([task("t1", "Write copy")]))
            : reply(200, paged([])),
    });
    const user = userEvent.setup();
    await renderDashboard();

    expect(await screen.findByText("Your tasks could not be loaded.")).toBeInTheDocument();
    failing = false;
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]);

    expect(await screen.findByText("Write copy", { selector: "p.truncate" })).toBeInTheDocument();
  });

  it("does not show a partial status breakdown when there are more projects than one page", async () => {
    serve(fetchMock, { ...healthy(), projects: () => reply(200, paged(projects, 150)) });
    await renderDashboard();

    expect(await screen.findByText(/more projects than one page holds/)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /To do:/ })).not.toBeInTheDocument();
  });

  it("says the list is partial when some projects were not checked", async () => {
    const many = Array.from({ length: 12 }, (_, i) => project(`p${i + 1}`, `Project ${i + 1}`));
    serve(fetchMock, { ...healthy(), projects: () => reply(200, paged(many)) });
    await renderDashboard();

    expect(await screen.findByText(/The total above is exact/)).toBeInTheDocument();
    const queried = new Set(
      urls(fetchMock)
        .filter((u) => u.includes("assignee_id"))
        .map((u) => u.split("/")[4]),
    );
    expect(queried.size).toBe(10);
  });
});

describe("quick actions and invalidation", () => {
  it("creating a project posts it and refreshes the dashboard data", async () => {
    let created = false;
    serve(fetchMock, {
      ...healthy(),
      stats: () => reply(200, { data: stats({ total_projects: created ? 3 : 2 }) }),
      post: (url, body) => {
        expect(url.pathname).toBe("/api/v1/projects");
        expect(body).toEqual({ name: "Roadmap", description: "Plans" });
        created = true;
        return reply(201, { data: project("p3", "Roadmap") });
      },
    });
    const user = userEvent.setup();
    await renderDashboard();
    await screen.findByText("Old site");
    const statsCalls = () => urls(fetchMock).filter((u) => u.endsWith("/dashboard/stats")).length;
    const before = statsCalls();

    await user.click(screen.getByRole("button", { name: /New/ }));
    await user.click(await screen.findByRole("menuitem", { name: "New project" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Roadmap");
    await user.type(within(dialog).getByLabelText("Description (optional)"), "Plans");
    await user.click(within(dialog).getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(statsCalls()).toBeGreaterThan(before));
    const grid = screen.getByRole("region", { name: "Statistics" });
    await waitFor(() =>
      expect(within(grid).getByText("Total projects").parentElement).toHaveTextContent("3"),
    );
  });

  it("validates the project name before sending", async () => {
    serve(fetchMock, healthy());
    const user = userEvent.setup();
    await renderDashboard();

    await user.click(screen.getByRole("button", { name: /New/ }));
    await user.click(await screen.findByRole("menuitem", { name: "New project" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Create project" }),
    );

    expect(await screen.findByText("Enter a project name")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("creates a task in a chosen project and offers only projects that allow it", async () => {
    let posted: { url: string; body: unknown } | null = null;
    serve(fetchMock, {
      ...healthy(),
      post: (url, body) => {
        posted = { url: url.pathname, body };
        return reply(201, { data: task("t9", "Plan sprint", { project_id: "p1" }) });
      },
    });
    const user = userEvent.setup();
    await renderDashboard();
    await screen.findByText("Old site");

    await user.click(screen.getByRole("button", { name: /New/ }));
    await user.click(await screen.findByRole("menuitem", { name: "New task" }));
    const dialog = await screen.findByRole("dialog");
    const select = within(dialog).getByLabelText("Project");
    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Choose a project",
      "Website redesign", // "Old site" does not allow create_task
    ]);
    await user.selectOptions(select, "p1");
    await user.type(within(dialog).getByLabelText("Title"), "Plan sprint");
    await user.selectOptions(within(dialog).getByLabelText("Priority"), "high");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted).toEqual({
      url: "/api/v1/projects/p1/tasks",
      body: { title: "Plan sprint", priority: "high" },
    });
  });
});
