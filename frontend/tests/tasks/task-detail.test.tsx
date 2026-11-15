import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TaskDetailView } from "@/features/tasks/task-detail-view";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "../api/helpers";
import { nav, renderWithAuth, resetNav } from "../auth/utils";
import { calls, detail, failure, member, route } from "../projects/fixtures";
import { ben, me, task } from "./fixtures";

vi.mock("next/navigation", async () => (await import("../auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;
const TASK = "GET /api/v1/tasks/t1";
const PROJECT = "GET /api/v1/projects/p1";

beforeEach(() => {
  resetNav("/projects/p1/tasks/t1");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const projectReply = () =>
  reply(200, {
    data: detail("p1", "Website redesign", { members: [member(me, true), member(ben)] }),
  });
const renderDetail = () => renderWithAuth(<TaskDetailView projectId="p1" taskId="t1" />);

const full = (extra: object = {}) =>
  task("t1", "Write copy", {
    priority: "high",
    due_date: "2000-01-01",
    allowed_actions: ["update", "delete", "complete"],
    ...extra,
  });

describe("access", () => {
  it("says 'not found' when the task does not exist or its project is not the user's", async () => {
    route(fetchMock, {
      [TASK]: () => failure(404, "NOT_FOUND", "Resource not found."),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(await screen.findByText("Task not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /All tasks/ })).toHaveAttribute(
      "href",
      "/projects/p1/tasks",
    );
  });

  it("does not show a task under a project it does not belong to", async () => {
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full({ project_id: "other" }) }),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(
      await screen.findByText("This task does not belong to this project."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Write copy")).not.toBeInTheDocument();
  });

  it("shows permission denied for a 403 and keeps the backend's reason", async () => {
    route(fetchMock, {
      [TASK]: () => failure(403, "FORBIDDEN", "Not yours.", "task-view"),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(screen.getByText(/Not yours\./)).toBeInTheDocument();
  });

  it("shows a skeleton, then a retryable error for a server failure", async () => {
    let failing = true;
    route(fetchMock, {
      [TASK]: () =>
        failing
          ? failure(500, "INTERNAL_ERROR", "Something went wrong.")
          : reply(200, { data: full() }),
      [PROJECT]: projectReply,
    });
    const user = userEvent.setup();
    renderDetail();

    expect(await screen.findByLabelText("Loading task")).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Something went wrong.",
    );
    failing = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Write copy" }),
    ).toBeInTheDocument();
  });
});

describe("details", () => {
  it("shows every field of the task", async () => {
    route(fetchMock, {
      [TASK]: () =>
        reply(200, { data: full({ assignee: ben, description: "Line one\nLine two" }) }),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Write copy" }),
    ).toBeInTheDocument();
    expect(screen.getByText("In Website redesign")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Ben Carter")).toBeInTheDocument();
    expect(screen.getByText("ben@example.com")).toBeInTheDocument();
    expect(screen.getByText(/Jan 1 · \d+ days overdue/)).toBeInTheDocument();
    expect(screen.getByText("Created by")).toBeInTheDocument();
    expect(screen.getByText(/Line one/)).toBeInTheDocument();
    expect(screen.getByLabelText("Status of Write copy")).toHaveValue("todo");
  });

  it("shows placeholders for empty fields, and the completion date once completed", async () => {
    route(fetchMock, {
      [TASK]: () =>
        reply(200, {
          data: full({
            assignee: null,
            description: null,
            due_date: null,
            status: "completed",
            completed_at: "2026-11-10T12:00:00Z",
            allowed_actions: ["update"],
          }),
        }),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(await screen.findByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("No due date")).toBeInTheDocument();
    expect(screen.getByText("No description")).toBeInTheDocument();
    expect(screen.getByText("Nov 10, 2026")).toBeInTheDocument();
  });
});

describe("what the backend allows", () => {
  it("shows Edit and Delete only when the task lists update and delete", async () => {
    route(fetchMock, { [TASK]: () => reply(200, { data: full() }), [PROJECT]: projectReply });
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("is read-only for someone with no actions: nothing to click, status locked", async () => {
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full({ allowed_actions: [] }) }),
      [PROJECT]: projectReply,
    });
    renderDetail();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Status of Write copy")).toBeDisabled();
    expect(screen.getByText("You have read-only access to this task.")).toBeInTheDocument();
  });

  it("explains why completing is unavailable, without listing the policy's fields", async () => {
    route(fetchMock, {
      [TASK]: () =>
        reply(200, { data: full({ status: "in_progress", allowed_actions: ["update"] }) }),
      [PROJECT]: projectReply,
    });
    renderDetail();

    expect(await screen.findByText(/Completing is not available until/)).toBeInTheDocument();
    const options = within(screen.getByLabelText("Status of Write copy")).getAllByRole(
      "option",
    ) as HTMLOptionElement[];
    expect(options.find((o) => o.value === "completed")?.disabled).toBe(true);
  });
});

describe("changing things", () => {
  it("moves the status and shows the new one", async () => {
    let status = "todo";
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full({ status }) }),
      [PROJECT]: projectReply,
      "PATCH /api/v1/tasks/t1/status": (_u, init) => {
        expect(JSON.parse(String(init?.body))).toEqual({ status: "in_progress" });
        status = "in_progress";
        return reply(200, { data: full({ status }) });
      },
    });
    const user = userEvent.setup();
    renderDetail();
    await user.selectOptions(await screen.findByLabelText("Status of Write copy"), "in_progress");

    await waitFor(() =>
      expect(screen.getByLabelText("Status of Write copy")).toHaveValue("in_progress"),
    );
  });

  it("shows a refused status change as an alert", async () => {
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full({ status: "in_progress" }) }),
      [PROJECT]: projectReply,
      "PATCH /api/v1/tasks/t1/status": () =>
        failure(
          403,
          "FORBIDDEN",
          "A task can be completed only when it has an assignee.",
          "task-complete",
        ),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.selectOptions(await screen.findByLabelText("Status of Write copy"), "completed");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. A task can be completed only when it has an assignee.",
    );
  });

  it("edits the task from the dialog, sending only what changed", async () => {
    let patched: unknown;
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full() }),
      [PROJECT]: projectReply,
      "PATCH /api/v1/tasks/t1": (_u, init) => {
        patched = JSON.parse(String(init?.body));
        return reply(200, { data: full() });
      },
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Assignee")).toHaveValue("u2");
    await user.selectOptions(within(dialog).getByLabelText("Priority"), "low");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patched).toEqual({ priority: "low" });
  });

  it("deletes after confirmation and returns to the list", async () => {
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full() }),
      [PROJECT]: projectReply,
      "DELETE /api/v1/tasks/t1": () => reply(204),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(calls(fetchMock, "DELETE", "/tasks/t1")).toHaveLength(0);
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete task" }),
    );

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/projects/p1/tasks"));
  });

  it("explains a refused delete and stays on the page", async () => {
    route(fetchMock, {
      [TASK]: () => reply(200, { data: full() }),
      [PROJECT]: projectReply,
      "DELETE /api/v1/tasks/t1": () =>
        failure(
          403,
          "FORBIDDEN",
          "Only the project owner can delete a task, and only while its status is todo.",
          "task-delete",
        ),
    });
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete task" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "You do not have permission to do this. Only the project owner can delete a task",
    );
    expect(nav.replace).not.toHaveBeenCalled();
  });
});
