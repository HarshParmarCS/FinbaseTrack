import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectsView } from "@/features/projects/projects-view";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { nav, renderWithAuth, resetNav } from "../auth/utils";
import { ben, calls, csrfOf, detail, failure, paged, project, route } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;

beforeEach(() => {
  resetNav("/projects");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const owned = project("p1", "Website redesign", { description: "Q4 launch", member_count: 3 });
const joined = project("p2", "Mobile app", {
  owner: ben,
  allowed_actions: ["create_task"],
  member_count: 1,
  description: null,
});
const archived = project("p3", "Old site", { status: "archived", allowed_actions: ["update"] });

async function renderList() {
  const view = renderWithAuth(<ProjectsView />);
  await screen.findByRole("heading", { level: 1, name: "Projects" });
  return view;
}

const openMenu = async (user: ReturnType<typeof userEvent.setup>, name: string) =>
  user.click(await screen.findByRole("button", { name: `Actions for ${name}` }));

describe("listing", () => {
  it("shows name, description, owner, member count, created date and status on each card", async () => {
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([owned, joined, archived])),
    });
    await renderList();

    const list = await screen.findByRole("list", { name: "Projects" });
    const cards = within(list).getAllByRole("listitem");
    expect(cards).toHaveLength(3);

    const first = cards[0];
    expect(within(first).getByRole("link", { name: "Website redesign" })).toHaveAttribute(
      "href",
      "/projects/p1",
    );
    expect(within(first).getByText("Q4 launch")).toBeInTheDocument();
    expect(within(first).getByText("You")).toBeInTheDocument(); // I own it
    expect(within(first).getByText("3 members")).toBeInTheDocument();
    expect(within(first).getByText("Nov 1, 2026")).toBeInTheDocument();
    expect(within(first).getByText("3 open · 3 done")).toBeInTheDocument();
    expect(within(first).getByText("Active")).toBeInTheDocument();

    expect(within(cards[1]).getByText("Ben Carter")).toBeInTheDocument(); // someone else owns it
    expect(within(cards[1]).getByText("No description")).toBeInTheDocument();
    expect(within(cards[1]).getByText("1 member")).toBeInTheDocument();
    expect(within(cards[2]).getByText("Archived")).toBeInTheDocument();
  });

  it("asks the backend for one page of the filters in the URL", async () => {
    resetNav("/projects", "?q=web&status=archived&page=2");
    route(fetchMock, {
      "GET /api/v1/projects": () =>
        reply(200, paged([owned], { page: 2, total: 13, total_pages: 2 })),
    });
    await renderList();
    await screen.findByRole("list", { name: "Projects" });

    const url = String(calls(fetchMock, "GET", "/api/v1/projects")[0][0]);
    expect(url).toBe("/api/v1/projects?q=web&status=archived&page=2&page_size=12");
    expect(screen.getByLabelText("Search projects")).toHaveValue("web");
    expect(screen.getByLabelText("Filter by status")).toHaveValue("archived");
  });

  it("puts a settled search term and a status filter in the URL, back on page 1", async () => {
    resetNav("/projects", "?page=3");
    route(fetchMock, { "GET /api/v1/projects": () => reply(200, paged([owned])) });
    const user = userEvent.setup();
    await renderList();
    await screen.findByRole("list", { name: "Projects" });

    await user.selectOptions(screen.getByLabelText("Filter by status"), "active");
    expect(nav.replace).toHaveBeenLastCalledWith("/projects?status=active");

    await user.type(screen.getByLabelText("Search projects"), "road");
    await waitFor(() => expect(nav.replace).toHaveBeenLastCalledWith("/projects?q=road"), {
      timeout: 2000,
    });
  });

  it("pages through results", async () => {
    route(fetchMock, {
      "GET /api/v1/projects": () =>
        reply(200, paged([owned], { page: 1, total: 30, total_pages: 3 })),
    });
    const user = userEvent.setup();
    await renderList();

    expect(await screen.findByText("Page 1 of 3 · 30 in total")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects?page=2");
  });

  it("explains an empty account and offers to create the first project", async () => {
    route(fetchMock, { "GET /api/v1/projects": () => reply(200, paged([])) });
    await renderList();

    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
  });

  it("explains an empty search and clears the filters", async () => {
    resetNav("/projects", "?q=zzz");
    route(fetchMock, { "GET /api/v1/projects": () => reply(200, paged([])) });
    const user = userEvent.setup();
    await renderList();

    expect(await screen.findByText("No projects match")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/projects");
  });

  it("shows a skeleton while loading, then an error with retry", async () => {
    let failing = true;
    route(fetchMock, {
      "GET /api/v1/projects": () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong on our side.")
          : reply(200, paged([owned])),
    });
    const user = userEvent.setup();
    renderWithAuth(<ProjectsView />);

    expect(await screen.findByLabelText("Loading projects")).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: "Website redesign" })).toBeInTheDocument();
  });
});

describe("actions follow what the backend allows", () => {
  const list = () =>
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([owned, joined, archived])),
    });

  it("offers Edit and Delete when allowed, Edit only when only update is allowed, neither otherwise", async () => {
    list();
    const user = userEvent.setup();
    await renderList();

    await openMenu(user, "Website redesign");
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await openMenu(user, "Mobile app");
    expect(await screen.findByRole("menuitem", { name: "Open" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");

    await openMenu(user, "Old site");
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
  });
});

describe("create", () => {
  it("creates a project and opens it", async () => {
    let body: unknown;
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([])),
      "POST /api/v1/projects": (_url, init) => {
        body = JSON.parse(String(init?.body));
        return reply(201, { data: detail("p9", "Roadmap") });
      },
    });
    const user = userEvent.setup();
    await renderList();
    await screen.findByText("No projects yet");

    await user.click(screen.getAllByRole("button", { name: "New project" })[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Roadmap");
    await user.click(within(dialog).getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/projects/p9"));
    expect(body).toEqual({ name: "Roadmap" });
  });

  it("shows a permission message when the backend refuses", async () => {
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([])),
      "POST /api/v1/projects": () =>
        failure(403, "FORBIDDEN", "Not allowed to create projects.", "project-create"),
    });
    const user = userEvent.setup();
    await renderList();
    await screen.findByText("No projects yet");

    await user.click(screen.getAllByRole("button", { name: "New project" })[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "X");
    await user.click(within(dialog).getByRole("button", { name: "Create project" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Not allowed to create projects.",
    );
  });
});

describe("edit", () => {
  it("sends only what changed and refreshes the list", async () => {
    let listCalls = 0;
    let patch: { url: string; body: unknown; csrf: string | null } | null = null;
    route(fetchMock, {
      "GET /api/v1/projects": () => {
        listCalls += 1;
        return reply(200, paged([owned]));
      },
      "PATCH /api/v1/projects/p1": (url, init) => {
        patch = { url: url.pathname, body: JSON.parse(String(init?.body)), csrf: csrfOf(init) };
        return reply(200, { data: detail("p1", "Website v2") });
      },
    });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Edit" }));

    const dialog = await screen.findByRole("dialog");
    const name = within(dialog).getByLabelText("Name");
    expect(name).toHaveValue("Website redesign");
    await user.clear(name);
    await user.type(name, "Website v2");
    await user.clear(within(dialog).getByLabelText("Description"));
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patch).toEqual({
      url: "/api/v1/projects/p1",
      body: { name: "Website v2", description: null },
      csrf: "tok",
    });
    await waitFor(() => expect(listCalls).toBe(2));
  });

  it("sends nothing when nothing changed", async () => {
    route(fetchMock, { "GET /api/v1/projects": () => reply(200, paged([owned])) });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Edit" }));

    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Save changes" }),
    );

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls(fetchMock, "PATCH", "/projects")).toHaveLength(0);
  });

  it("shows the backend's permission denial inside the dialog", async () => {
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([owned])),
      "PATCH /api/v1/projects/p1": () =>
        failure(403, "FORBIDDEN", "Only the project owner can update a project.", "project-update"),
    });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), " 2");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the project owner can update a project.",
    );
  });
});

describe("delete", () => {
  it("asks first, warns about the consequences, and sends nothing on cancel", async () => {
    route(fetchMock, { "GET /api/v1/projects": () => reply(200, paged([owned])) });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Delete “Website redesign”?")).toBeInTheDocument();
    expect(within(dialog).getByText(/all of its tasks and members/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(calls(fetchMock, "DELETE", "/projects")).toHaveLength(0);
  });

  it("deletes with the CSRF header and refreshes the list", async () => {
    let remaining = [owned];
    let csrf: string | null = null;
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged(remaining)),
      "DELETE /api/v1/projects/p1": (_url, init) => {
        csrf = csrfOf(init);
        remaining = [];
        return reply(204);
      },
    });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Delete project",
      }),
    );

    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    expect(csrf).toBe("tok");
  });

  it("shows a clear permission message when the backend denies the delete", async () => {
    route(fetchMock, {
      "GET /api/v1/projects": () => reply(200, paged([owned])),
      "DELETE /api/v1/projects/p1": () =>
        failure(403, "FORBIDDEN", "Only the project owner can delete a project.", "project-delete"),
    });
    const user = userEvent.setup();
    await renderList();
    await openMenu(user, "Website redesign");
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete project" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the project owner can delete a project.",
    );
    // The page behind an open dialog is hidden from the accessibility tree, hence `hidden`.
    expect(
      screen.getByRole("link", { name: "Website redesign", hidden: true }),
    ).toBeInTheDocument();
  });
});
