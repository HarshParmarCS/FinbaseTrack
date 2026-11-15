import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActivityView } from "@/features/activity/activity-view";
import { ProjectDetailView } from "@/features/projects/project-detail-view";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { renderWithAuth, resetNav } from "../auth/utils";
import { ben, calls, detail, failure, me, member, project, route } from "../projects/fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;
const NOW = new Date(2026, 10, 15, 18, 0);
const FEED = "GET /api/v1/dashboard/activity";
const PROJECTS = "GET /api/v1/projects";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetNav("/activity");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const at = (d: number, h: number) => new Date(2026, 10, d, h).toISOString();
const ev = (id: string, action: string, metadata: object, created: string, extra: object = {}) => ({
  id,
  user: ben,
  project_id: "p1",
  task_id: action.startsWith("task.") ? "t1" : null,
  action,
  metadata,
  created_at: created,
  ...extra,
});

const page = (data: unknown[], p = 1, total = data.length, totalPages = 1) => ({
  data,
  meta: { page: p, page_size: 20, total, total_pages: totalPages },
});

const newestFirst = [
  ev("e3", "task.status_changed", { from: "todo", to: "in_progress", position: 2 }, at(15, 16)),
  ev("e2", "task.created", { title: "Write copy" }, at(15, 9), { user: me }),
  ev("e1", "project.created", { name: "Website" }, at(14, 11), { user: me }),
];

const projectsList = () =>
  reply(200, {
    data: [project("p1", "Website")],
    meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
  });

describe("activity page", () => {
  it("shows a timeline grouped by day, newest first, with actors, links and readable times", async () => {
    route(fetchMock, { [FEED]: () => reply(200, page(newestFirst)), [PROJECTS]: projectsList });
    renderWithAuth(<ActivityView />);

    const today = await screen.findByRole("region", { name: "Today" });
    const items = within(today).getAllByRole("listitem");
    expect(items.map((li) => li.querySelector("p")?.textContent)).toEqual([
      "Ben Carter moved Write copy from To do to In progress in Website",
      "You created the task Write copy in Website",
    ]);
    expect(within(items[0]).getByRole("link", { name: "Write copy" })).toHaveAttribute(
      "href",
      "/projects/p1/tasks/t1",
    );
    expect(within(items[0]).getByRole("link", { name: "Website" })).toHaveAttribute(
      "href",
      "/projects/p1",
    );
    const time = items[0].querySelector("time");
    expect(time).toHaveAttribute("datetime", at(15, 16));
    expect(time?.textContent).toMatch(/^4:00 PM, Sunday, November 15, 2026 at 4:00 PM$/);
    const yesterday = screen.getByRole("region", { name: "Yesterday" });
    expect(within(yesterday).getByText(/created the project/)).toBeInTheDocument();
    expect(screen.getByText("Showing 3 of 3")).toBeInTheDocument();
  });

  it("asks the backend for the first page of 20 and loads the next page on request", async () => {
    route(fetchMock, {
      [FEED]: (url) =>
        url.searchParams.get("page") === "2"
          ? reply(200, page([newestFirst[2]], 2, 3, 2))
          : reply(200, page(newestFirst.slice(0, 2), 1, 3, 2)),
      [PROJECTS]: projectsList,
    });
    const user = userEvent.setup();
    renderWithAuth(<ActivityView />);

    expect(await screen.findByText("Showing 2 of 3")).toBeInTheDocument();
    expect(String(calls(fetchMock, "GET", "/dashboard/activity")[0][0])).toBe(
      "/api/v1/dashboard/activity?page=1&page_size=20",
    );
    await user.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText("Showing 3 of 3")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Yesterday" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("does not repeat an entry that shifted onto the next page", async () => {
    route(fetchMock, {
      [FEED]: (url) =>
        url.searchParams.get("page") === "2"
          ? reply(200, page([newestFirst[1], newestFirst[2]], 2, 3, 2))
          : reply(200, page(newestFirst.slice(0, 2), 1, 3, 2)),
      [PROJECTS]: projectsList,
    });
    const user = userEvent.setup();
    renderWithAuth(<ActivityView />);
    await user.click(await screen.findByRole("button", { name: "Load more" }));

    await screen.findByRole("region", { name: "Yesterday" });
    expect(screen.getAllByText(/created the task/)).toHaveLength(1);
  });

  it("shows a skeleton while loading", async () => {
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/me")
        ? reply(200, { data: me })
        : new Promise<Response>(() => {}),
    );
    renderWithAuth(<ActivityView />);

    expect(await screen.findByLabelText("Loading activity")).toBeInTheDocument();
  });

  it("explains an empty feed", async () => {
    route(fetchMock, { [FEED]: () => reply(200, page([], 1, 0, 0)), [PROJECTS]: projectsList });
    renderWithAuth(<ActivityView />);

    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
  });

  it("shows an error with retry", async () => {
    let failing = true;
    route(fetchMock, {
      [FEED]: () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong on our side.")
          : reply(200, page(newestFirst)),
      [PROJECTS]: projectsList,
    });
    const user = userEvent.setup();
    renderWithAuth(<ActivityView />);

    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("region", { name: "Today" })).toBeInTheDocument();
  });

  it("keeps the loaded entries and says so when loading more fails", async () => {
    route(fetchMock, {
      [FEED]: (url) =>
        url.searchParams.get("page") === "2"
          ? failure(500, "INTERNAL_ERROR", "Something went wrong on our side.")
          : reply(200, page(newestFirst.slice(0, 2), 1, 3, 2)),
      [PROJECTS]: projectsList,
    });
    const user = userEvent.setup();
    renderWithAuth(<ActivityView />);
    await user.click(await screen.findByRole("button", { name: "Load more" }));

    expect(
      await screen.findByText(/More activity could not be loaded/, {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Today" })).toBeInTheDocument();
  });
});

describe("project timeline on the project page", () => {
  it("lists only that project's events, without repeating the project name, naming members", async () => {
    resetNav("/projects/p1");
    route(fetchMock, {
      "GET /api/v1/projects/p1": () =>
        reply(200, { data: detail("p1", "Website", { members: [member(me, true), member(ben)] }) }),
      "GET /api/v1/projects/p1/activity": () =>
        reply(
          200,
          page([
            ev("m1", "member.added", { member_user_id: "u2" }, at(15, 12), { user: me }),
            ev("t1", "task.deleted", { title: "Throwaway", status: "todo" }, at(15, 11)),
          ]),
        ),
    });
    renderWithAuth(<ProjectDetailView projectId="p1" />);

    const timeline = (await screen.findByRole("heading", { level: 2, name: "Activity" })).closest(
      '[data-slot="card"]',
    ) as HTMLElement;
    const lines = (await within(timeline).findAllByRole("listitem")).map(
      (li) => li.querySelector("p")?.textContent,
    );
    expect(lines).toEqual([
      "You added Ben Carter to Website",
      "Ben Carter deleted the task Throwaway",
    ]);
    expect(within(timeline).queryByRole("link", { name: "Throwaway" })).not.toBeInTheDocument(); // it is gone
    await waitFor(() =>
      expect(String(calls(fetchMock, "GET", "/projects/p1/activity")[0][0])).toBe(
        "/api/v1/projects/p1/activity?page=1&page_size=20",
      ),
    );
  });
});

describe("names load before entries show", () => {
  it("keeps the skeleton until the project list has arrived, so no stand-in name flashes", async () => {
    let releaseProjects: () => void = () => undefined;
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return reply(200, { data: me });
      if (url.includes("/dashboard/activity")) return reply(200, page(newestFirst));
      if (url.includes("/api/v1/projects")) {
        await new Promise<void>((resolve) => (releaseProjects = resolve));
        return projectsList();
      }
      throw new Error(url);
    });
    renderWithAuth(<ActivityView />);

    expect(await screen.findByLabelText("Loading activity")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText(/can no longer open|a project/)).not.toBeInTheDocument();
    releaseProjects();

    const today = await screen.findByRole("region", { name: "Today" });
    expect(within(today).getAllByRole("link", { name: "Website" }).length).toBeGreaterThan(0);
  });
});
