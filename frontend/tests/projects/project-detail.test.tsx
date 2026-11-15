import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectDetailView } from "@/features/projects/project-detail-view";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { nav, renderWithAuth, resetNav } from "../auth/utils";
import { ben, calls, csrfOf, cy, detail, failure, member, route } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;
const URL_P1 = "GET /api/v1/projects/p1";

beforeEach(() => {
  resetNav("/projects/p1");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const renderDetail = () => renderWithAuth(<ProjectDetailView projectId="p1" />);

/** A project where the signed-in user (Ana) is only a member: no manage actions. */
const asMember = () =>
  detail("p1", "Website redesign", {
    owner: ben,
    allowed_actions: ["create_task"],
    members: [member(ben, true), member({ id: "u1", email: "ana@example.com", name: "Ana Lopez" })],
  });

describe("access", () => {
  it("shows 'not found' for a project that does not exist or that the user is not in", async () => {
    route(fetchMock, { [URL_P1]: () => failure(404, "NOT_FOUND", "Resource not found.") });
    renderDetail();

    expect(await screen.findByText("Project not found")).toBeInTheDocument();
    expect(screen.getByText(/does not exist, or you are not a member/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your projects" })).toHaveAttribute(
      "href",
      "/projects",
    );
    expect(screen.queryByRole("button", { name: /Edit|Delete/ })).not.toBeInTheDocument();
  });

  it("shows a permission-denied page for a 403 and keeps the backend's reason", async () => {
    route(fetchMock, {
      [URL_P1]: () => failure(403, "FORBIDDEN", "You cannot view this.", "project-view"),
    });
    renderDetail();

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(screen.getByText(/You cannot view this\./)).toBeInTheDocument();
  });

  it("shows a retryable error for a server failure", async () => {
    let failing = true;
    route(fetchMock, {
      [URL_P1]: () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong.")
          : reply(200, { data: detail("p1", "Back again") }),
    });
    const user = userEvent.setup();
    renderDetail();

    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong.",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Back again" }),
    ).toBeInTheDocument();
  });

  it("shows a loading skeleton first", async () => {
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/me")
        ? reply(200, { data: { id: "u1", email: "a@b.co", name: "Ana" } })
        : new Promise<Response>(() => {}),
    );
    renderDetail();

    expect(await screen.findByLabelText("Loading project")).toBeInTheDocument();
  });
});

describe("details", () => {
  it("shows the project, its owner, members and task progress", async () => {
    route(fetchMock, { [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }) });
    renderDetail();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
    ).toBeInTheDocument();
    expect(screen.getByText("About Website redesign")).toBeInTheDocument();
    expect(screen.getByText("Nov 1, 2026")).toBeInTheDocument();
    expect(screen.getByText("2 to do · 1 in progress · 3 completed")).toBeInTheDocument();
    const members = within(screen.getByRole("list", { name: "Project members" })).getAllByRole(
      "listitem",
    );
    expect(members).toHaveLength(2);
    expect(within(members[0]).getByText("Owner")).toBeInTheDocument();
    expect(within(members[0]).getByText("You")).toBeInTheDocument();
    expect(within(members[1]).getByText("Ben Carter")).toBeInTheDocument();
    expect(within(members[1]).getByText("ben@example.com")).toBeInTheDocument();
  });

  it("gives the owner every control, except removing the owner", async () => {
    route(fetchMock, { [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }) });
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Add member" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Ben Carter" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Ana Lopez" })).not.toBeInTheDocument();
  });

  it("hides every management control from a member the backend does not allow to manage", async () => {
    route(fetchMock, { [URL_P1]: () => reply(200, { data: asMember() }) });
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Add member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Remove/ })).not.toBeInTheDocument();
    // Members are still visible to every member.
    const list = screen.getByRole("list", { name: "Project members" });
    expect(within(list).getByText("Ben Carter")).toBeInTheDocument();
  });
});

describe("update and delete", () => {
  it("updates the project and shows the new values", async () => {
    let current = detail("p1", "Website redesign");
    route(fetchMock, {
      [URL_P1]: () => reply(200, { data: current }),
      "PATCH /api/v1/projects/p1": (_u, init) => {
        expect(JSON.parse(String(init?.body))).toEqual({ status: "archived" });
        current = { ...current, status: "archived" };
        return reply(200, { data: current });
      },
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Status"), "archived");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await screen.findByText("Archived")).toBeInTheDocument();
  });

  it("deletes after confirmation and returns to the list", async () => {
    route(fetchMock, {
      [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }),
      "DELETE /api/v1/projects/p1": () => reply(204),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(calls(fetchMock, "DELETE", "/projects/p1")).toHaveLength(0); // not before confirming
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Delete project",
      }),
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/projects"));
    expect(calls(fetchMock, "DELETE", "/projects/p1")).toHaveLength(1);
  });

  it("explains a permission denial instead of leaving the page", async () => {
    route(fetchMock, {
      [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }),
      "DELETE /api/v1/projects/p1": () =>
        failure(403, "FORBIDDEN", "Only the project owner can delete a project.", "project-delete"),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete project" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the project owner can delete a project.",
    );
    expect(nav.replace).not.toHaveBeenCalled();
  });
});

describe("adding members", () => {
  const withMembers = (members: ReturnType<typeof member>[]) => () =>
    reply(200, {
      data: detail("p1", "Website redesign", { members, member_count: members.length }),
    });

  it("adds a member by email and shows them in the list", async () => {
    let members = [member({ id: "u1", email: "ana@example.com", name: "Ana Lopez" }, true)];
    let sent: { body: unknown; csrf: string | null } | null = null;
    route(fetchMock, {
      [URL_P1]: () => withMembers(members)(),
      "POST /api/v1/projects/p1/members": (_u, init) => {
        sent = { body: JSON.parse(String(init?.body)), csrf: csrfOf(init) };
        members = [...members, member(ben)];
        return reply(201, { data: member(ben) });
      },
    });
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    await user.type(screen.getByLabelText("Add a member by email"), " ben@example.com ");
    await user.click(screen.getByRole("button", { name: "Add member" }));

    expect(await screen.findByText("Ben Carter was added to the project")).toBeInTheDocument();
    expect(sent).toEqual({ body: { email: "ben@example.com" }, csrf: "tok" });
    expect(await screen.findByText("ben@example.com")).toBeInTheDocument();
    expect(screen.getByLabelText("Add a member by email")).toHaveValue("");
  });

  it("validates the email before sending", async () => {
    route(fetchMock, { [URL_P1]: withMembers([member(ben, true)]) });
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    await user.type(screen.getByLabelText("Add a member by email"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Add member" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(calls(fetchMock, "POST", "/members")).toHaveLength(0);
  });

  it.each([
    [404, "NOT_FOUND", "User not found.", undefined, /No registered user has that email address/],
    [
      409,
      "CONFLICT",
      "That user is already a member of this project.",
      undefined,
      /already a member/,
    ],
    [
      403,
      "FORBIDDEN",
      "Only the project owner can add or remove project members.",
      "project-member-manage",
      /You do not have permission to do this\. Only the project owner/,
    ],
  ])("explains a %i answer", async (status, code, message, policy, expected) => {
    route(fetchMock, {
      [URL_P1]: withMembers([
        member({ id: "u1", email: "ana@example.com", name: "Ana Lopez" }, true),
      ]),
      "POST /api/v1/projects/p1/members": () => failure(status, code, message, policy),
    });
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    await user.type(screen.getByLabelText("Add a member by email"), "cy@example.com");
    await user.click(screen.getByRole("button", { name: "Add member" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(expected);
  });
});

describe("removing members", () => {
  it("confirms, explains the effect on tasks, then removes", async () => {
    let members = [
      member({ id: "u1", email: "ana@example.com", name: "Ana Lopez" }, true),
      member(ben),
      member(cy),
    ];
    let csrf: string | null = null;
    route(fetchMock, {
      [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign", { members }) }),
      "DELETE /api/v1/projects/p1/members/u2": (_u, init) => {
        csrf = csrfOf(init);
        members = members.filter((m) => m.user.id !== "u2");
        return reply(204);
      },
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Remove Ben Carter" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/lose access to this project immediately/)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/tasks assigned to them become unassigned/),
    ).toBeInTheDocument();
    expect(calls(fetchMock, "DELETE", "/members")).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Remove member" }));

    expect(await screen.findByText("Ben Carter was removed from the project")).toBeInTheDocument();
    expect(csrf).toBe("tok");
    await waitFor(() => expect(screen.queryByText("ben@example.com")).not.toBeInTheDocument());
    expect(screen.getByText("cy@example.com")).toBeInTheDocument();
  });

  it("does nothing when the confirmation is cancelled", async () => {
    route(fetchMock, { [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }) });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Remove Ben Carter" }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }),
    );

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(calls(fetchMock, "DELETE", "/members")).toHaveLength(0);
  });

  it("shows the backend's refusal, for example when the owner is targeted", async () => {
    route(fetchMock, {
      [URL_P1]: () => reply(200, { data: detail("p1", "Website redesign") }),
      "DELETE /api/v1/projects/p1/members/u2": () =>
        failure(
          403,
          "FORBIDDEN",
          "Only the project owner can add or remove project members.",
          "project-member-manage",
        ),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Remove Ben Carter" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Remove member" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      /You do not have permission to do this/,
    );
  });
});
