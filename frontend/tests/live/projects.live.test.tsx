/**
 * The Projects module against the REAL backend, through the real pages (rendered in jsdom) and
 * three real users: Ana (owner), Ben (member) and Cy (outsider). Nothing is mocked except the
 * Next.js router. Run with the backend up:  pnpm test:live
 * It registers three throwaway users and creates one project (deleted again by the last test).
 */
import { configure, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { CookieJar } from "./cookie-jar";

vi.mock("@/config/env", () => ({
  publicEnv: {
    NEXT_PUBLIC_API_BASE_URL: process.env.LIVE_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "live",
  },
}));
vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

import { register } from "@/features/auth/api";
import { ProjectDetailView } from "@/features/projects/project-detail-view";
import {
  addMember,
  deleteProject,
  getProject,
  listMembers,
  listProjects,
  removeMember,
  updateProject,
} from "@/features/projects/api";
import { ProjectsView } from "@/features/projects/projects-view";
import { getActionErrorMessage, isApiError, isPermissionDenied } from "@/lib/api/errors";
import type { UserOut } from "@/types/api";
import { nav, renderWithAuth, resetNav } from "../auth/utils";

configure({ asyncUtilTimeout: 8000 });

const origin = process.env.LIVE_ORIGIN ?? "http://localhost:3000";
const stamp = Date.now();
const password = "live-test-password-1";

type Person = { jar: CookieJar; email: string; name: string; user?: UserOut };
const person = (key: string, name: string): Person => ({
  jar: new CookieJar(origin),
  email: `projlive-${key}-${stamp}@example.com`,
  name,
});
const ana = person("ana", "Ana Owner");
const ben = person("ben", "Ben Member");
const cy = person("cy", "Cy Outsider");

/** Act as this person: their cookies, their readable csrf cookie. */
function as(who: Person) {
  vi.stubGlobal("fetch", who.jar.fetch);
  who.jar.activate();
}

async function failure(promise: Promise<unknown>) {
  const error = await promise.then(
    () => null,
    (caught: unknown) => caught,
  );
  if (!isApiError(error)) throw new Error(`expected an ApiError, got ${String(error)}`);
  return error;
}

let projectId = "";

beforeAll(async () => {
  for (const who of [ana, ben, cy]) {
    as(who);
    who.user = await register({ name: who.name, email: who.email, password });
  }
});

afterAll(async () => {
  if (projectId) {
    as(ana);
    await deleteProject(projectId).catch(() => undefined);
  }
  vi.unstubAllGlobals();
});

describe("owner: create, view and update through the pages", () => {
  it("starts with an empty project list and creates a project from the dialog", async () => {
    as(ana);
    resetNav("/projects");
    const user = userEvent.setup();
    renderWithAuth(<ProjectsView />);

    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "New project" })[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Live Website");
    await user.type(
      within(dialog).getByLabelText("Description (optional)"),
      "Created by a live test",
    );
    await user.click(within(dialog).getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    const target = String(nav.replace.mock.calls.at(-1)?.[0]);
    expect(target).toMatch(/^\/projects\/[0-9a-f-]{36}$/);
    projectId = target.split("/").pop() ?? "";
  });

  it("lists it with owner, member count and creation date, and offers owner actions", async () => {
    as(ana);
    resetNav("/projects");
    const user = userEvent.setup();
    renderWithAuth(<ProjectsView />);

    const card = (await screen.findByRole("link", { name: "Live Website" })).closest("li");
    expect(card).not.toBeNull();
    const view = within(card as HTMLElement);
    expect(view.getByText("You")).toBeInTheDocument();
    expect(view.getByText("1 member")).toBeInTheDocument();
    expect(view.getByText("Created by a live test")).toBeInTheDocument();
    expect(view.getByText(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/)).toBeInTheDocument();
    await user.click(view.getByRole("button", { name: "Actions for Live Website" }));
    expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
  });

  it("shows the project page, and edits only what changed (cleared description becomes empty)", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Live Website" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Name"));
    await user.type(within(dialog).getByLabelText("Name"), "Live Website v2");
    await user.clear(within(dialog).getByLabelText("Description"));
    await user.selectOptions(within(dialog).getByLabelText("Status"), "archived");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Live Website v2" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("No description")).toBeInTheDocument();
    const stored = await getProject(projectId);
    expect(stored).toMatchObject({
      name: "Live Website v2",
      description: null,
      status: "archived",
    });
  });

  it("filters the list by status and by name on the server", async () => {
    as(ana);
    expect((await listProjects({ status: "active" })).data).toHaveLength(0);
    expect((await listProjects({ status: "archived", q: "website" })).data).toHaveLength(1);
    expect((await listProjects({ q: "does-not-exist" })).meta.total).toBe(0);
    await updateProject(projectId, { status: "active" });
  });
});

describe("owner: membership through the page", () => {
  it("rejects a bad email locally, an unknown email and the owner themself with clear messages", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);
    await screen.findByRole("heading", { level: 1 });
    const input = screen.getByLabelText("Add a member by email");
    const add = screen.getByRole("button", { name: "Add member" });

    await user.type(input, "nope");
    await user.click(add);
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, `nobody-${stamp}@example.com`);
    await user.click(add);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /No registered user has that email address/,
    );

    await user.clear(input);
    await user.type(input, ana.email);
    await user.click(add);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/already a member/i));
  });

  it("adds Ben by email and lists him", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);
    await screen.findByRole("heading", { level: 1 });

    await user.type(screen.getByLabelText("Add a member by email"), ben.email);
    await user.click(screen.getByRole("button", { name: "Add member" }));

    expect(await screen.findByText("Ben Member was added to the project")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Project members" });
    expect(await within(list).findByText(ben.email)).toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);

    const again = await failure(addMember(projectId, { email: ben.email }));
    expect(again.status).toBe(409);
  });
});

describe("member: sees the project but the backend refuses management", () => {
  it("lists the shared project with the owner's name and no edit or delete in the menu", async () => {
    as(ben);
    resetNav("/projects");
    const user = userEvent.setup();
    renderWithAuth(<ProjectsView />);

    const card = (await screen.findByRole("link", { name: "Live Website v2" })).closest(
      "li",
    ) as HTMLElement;
    expect(within(card).getByText("Ana Owner")).toBeInTheDocument();
    expect(within(card).getByText("2 members")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Actions for Live Website v2" }));
    expect(await screen.findByRole("menuitem", { name: "Open" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("shows the members but no management controls on the project page", async () => {
    as(ben);
    resetNav(`/projects/${projectId}`);
    renderWithAuth(<ProjectDetailView projectId={projectId} />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Live Website v2" }),
    ).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Project members" });
    expect(within(list).getByText(ana.email)).toBeInTheDocument();
    expect(within(list).getByText("You")).toBeInTheDocument();
    for (const label of ["Edit", "Delete"]) {
      expect(screen.queryByRole("button", { name: label })).not.toBeInTheDocument();
    }
    expect(screen.queryByRole("form", { name: "Add member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Remove/ })).not.toBeInTheDocument();
  });

  it("is denied by the backend (403 with a policy) if he calls the APIs directly", async () => {
    as(ben);
    const attempts = {
      update: failure(updateProject(projectId, { name: "Hijacked" })),
      delete: failure(deleteProject(projectId)),
      add: failure(addMember(projectId, { email: cy.email })),
      removeOwner: failure(removeMember(projectId, ana.user?.id ?? "")),
    };

    for (const [name, pending] of Object.entries(attempts)) {
      const error = await pending;
      expect(error.status, name).toBe(403);
      expect(isPermissionDenied(error), name).toBe(true);
      expect(getActionErrorMessage(error), name).toMatch(
        /^You do not have permission to do this\. Only the project owner/,
      );
    }
    expect((await getProject(projectId)).name).toBe("Live Website v2"); // nothing changed
  });
});

describe("outsider: a project id in the URL grants nothing", () => {
  it("gets 'not found' on the page and an empty list", async () => {
    as(cy);
    resetNav(`/projects/${projectId}`);
    renderWithAuth(<ProjectDetailView projectId={projectId} />);

    expect(await screen.findByText("Project not found")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Edit|Delete/ })).not.toBeInTheDocument();
    expect((await listProjects({})).data).toHaveLength(0);
  });

  it("gets the same 404 for every API, so the project's existence is not revealed", async () => {
    as(cy);
    const checks = [
      failure(getProject(projectId)),
      failure(listMembers(projectId)),
      failure(updateProject(projectId, { name: "x" })),
      failure(deleteProject(projectId)),
      failure(getProject("00000000-0000-4000-8000-0000000000ff")),
    ];
    for (const error of await Promise.all(checks)) expect(error.status).toBe(404);
  });
});

describe("owner: removes a member and deletes the project through the page", () => {
  it("asks for confirmation, removes Ben, and Ben immediately loses access", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);
    await user.click(await screen.findByRole("button", { name: "Remove Ben Member" }));
    const dialog = await screen.findByRole("alertdialog");
    expect((await listMembers(projectId)).length).toBe(2); // nothing happened yet
    await user.click(within(dialog).getByRole("button", { name: "Remove member" }));

    expect(await screen.findByText("Ben Member was removed from the project")).toBeInTheDocument();
    expect((await listMembers(projectId)).map((m) => m.user.email)).toEqual([ana.email]);

    as(ben);
    expect((await failure(getProject(projectId))).status).toBe(404);
    expect((await listProjects({})).data).toHaveLength(0);
  });

  it("will not remove the owner", async () => {
    as(ana);
    const error = await failure(removeMember(projectId, ana.user?.id ?? ""));

    expect(error.status).toBe(422);
    expect(error.code).toBe("BUSINESS_RULE_VIOLATION");
  });

  it("deletes the project after confirmation and goes back to the list", async () => {
    as(ana);
    resetNav(`/projects/${projectId}`);
    const user = userEvent.setup();
    renderWithAuth(<ProjectDetailView projectId={projectId} />);
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/all of its tasks and members/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Delete project" }));

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/projects"));
    expect((await failure(getProject(projectId))).status).toBe(404);
    expect((await listProjects({})).data).toHaveLength(0);
    projectId = ""; // already gone; nothing to clean up
  });
});
