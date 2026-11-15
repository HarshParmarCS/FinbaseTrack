import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AppError from "@/app/(app)/error";
import { AppShell } from "@/components/layout/app-shell";
import { GlobalProgress } from "@/components/layout/global-progress";
import { QuickActions } from "@/features/dashboard/quick-actions";
import { AccountView } from "@/features/settings/account-view";
import { TaskStatusSelect } from "@/features/tasks/task-status-select";
import { clearCookie, reply, setCookie, stubFetch, type FetchMock } from "./api/helpers";
import { renderWithAuth, resetNav } from "./auth/utils";
import { ben, cy, detail, me, member, project, route } from "./projects/fixtures";
import { task } from "./tasks/fixtures";

vi.mock("next/navigation", async () => (await import("./auth/utils")).mockNextNavigation());

let fetchMock: FetchMock;

beforeEach(() => {
  resetNav("/dashboard");
  setCookie("csrf_token", "tok");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

describe("toasts", () => {
  it("confirm a successful status change", async () => {
    route(fetchMock, {
      "PATCH /api/v1/tasks/t1/status": () =>
        reply(200, { data: task("t1", "Write copy", { status: "in_progress" }) }),
    });
    const user = userEvent.setup();
    renderWithAuth(
      <TaskStatusSelect task={task("t1", "Write copy") as never} onError={() => undefined} />,
    );

    await user.selectOptions(await screen.findByLabelText("Status of Write copy"), "in_progress");

    expect(await screen.findByText("“Write copy” moved to In progress")).toBeInTheDocument();
  });

  it("are not used for failures, which are reported next to the control", async () => {
    const onError = vi.fn();
    route(fetchMock, {
      "PATCH /api/v1/tasks/t1/status": () =>
        reply(403, {
          error: {
            code: "FORBIDDEN",
            message: "No.",
            details: [{ field: null, message: "No.", policy_id: "task-update" }],
          },
        }),
    });
    const user = userEvent.setup();
    renderWithAuth(<TaskStatusSelect task={task("t1", "Write copy") as never} onError={onError} />);

    await user.selectOptions(await screen.findByLabelText("Status of Write copy"), "in_progress");

    await waitFor(() =>
      expect(onError).toHaveBeenCalledWith("You do not have permission to do this. No."),
    );
    expect(screen.queryByText(/moved to/)).not.toBeInTheDocument();
  });
});

describe("dashboard quick task uses the same task form", () => {
  it("offers allowed projects, then that project's members as assignees, and creates the task", async () => {
    let created: unknown;
    route(fetchMock, {
      "GET /api/v1/projects": () =>
        reply(200, {
          data: [project("p1", "Website"), project("p2", "Read only", { allowed_actions: [] })],
          meta: { page: 1, page_size: 100, total: 2, total_pages: 1 },
        }),
      "GET /api/v1/projects/p1": () =>
        reply(200, {
          data: detail("p1", "Website", { members: [member(me, true), member(ben), member(cy)] }),
        }),
      "POST /api/v1/projects/p1/tasks": (_u, init) => {
        created = JSON.parse(String(init?.body));
        return reply(201, { data: task("t9", "Plan sprint") });
      },
    });
    const user = userEvent.setup();
    renderWithAuth(<QuickActions />);

    await user.click(screen.getByRole("button", { name: /New/ }));
    await user.click(await screen.findByRole("menuitem", { name: "New task" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));
    expect(await within(dialog).findByText("Choose a project")).toBeInTheDocument();

    const projectSelect = within(dialog).getByLabelText("Project");
    await waitFor(() =>
      expect(
        within(projectSelect)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["Choose a project", "Website"]),
    );
    await user.selectOptions(projectSelect, "p1");
    const assignee = within(dialog).getByLabelText("Assignee");
    await waitFor(() =>
      expect(
        within(assignee)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["Unassigned", "Ana Lopez", "Ben Carter", "Cy Dunn"]),
    );
    await user.type(within(dialog).getByLabelText("Title"), "Plan sprint");
    await user.selectOptions(assignee, "u3");
    await user.click(within(dialog).getByRole("button", { name: "Create task" }));

    expect(await screen.findByText("Task “Plan sprint” created")).toBeInTheDocument();
    expect(created).toEqual({ title: "Plan sprint", priority: "medium", assignee_id: "u3" });
  });
});

describe("app shell accessibility", () => {
  it("has a skip link to the main content, which can take focus", async () => {
    route(fetchMock, {});
    const user = userEvent.setup();
    renderWithAuth(
      <AppShell>
        <p>page</p>
      </AppShell>,
    );

    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveAttribute("href", "#main-content");
    await user.tab();
    expect(skip).toHaveFocus(); // the first thing the keyboard reaches
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main-content");
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("complementary", { name: "Sidebar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument(); // phones
  });

  it("opens the mobile navigation from the keyboard and closes it after choosing a page", async () => {
    route(fetchMock, {});
    const user = userEvent.setup();
    renderWithAuth(
      <AppShell>
        <p>page</p>
      </AppShell>,
    );

    screen.getByRole("button", { name: "Open navigation" }).focus();
    await user.keyboard("{Enter}");
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("link", { name: "Projects" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("global loading bar", () => {
  it("is shown while a request is in flight and hidden from assistive technology", async () => {
    const client = new QueryClient();
    let release: () => void = () => undefined;
    render(
      <QueryClientProvider client={client}>
        <GlobalProgress />
      </QueryClientProvider>,
    );
    const bar = document.querySelector("[data-busy]");
    expect(bar).toHaveAttribute("data-busy", "false");

    act(() => {
      void client.fetchQuery({
        queryKey: ["slow"],
        queryFn: () => new Promise<number>((resolve) => (release = () => resolve(1))),
      });
    });
    await waitFor(() => expect(bar).toHaveAttribute("data-busy", "true"));
    act(() => release());
    await waitFor(() => expect(bar).toHaveAttribute("data-busy", "false"));
    expect(bar?.parentElement).toHaveAttribute("aria-hidden", "true");
  });
});

describe("error boundary", () => {
  it("shows a recovery screen without leaking the error, and retries", async () => {
    const retry = vi.fn();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const user = userEvent.setup();
    render(<AppError error={new Error("secret stack detail")} retry={retry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.queryByText(/secret stack detail/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    consoleError.mockRestore();
  });
});

describe("settings", () => {
  it("shows the signed-in account from the backend and says editing is not available", async () => {
    route(fetchMock, {});
    renderWithAuth(<AccountView />);

    expect(await screen.findByText("Ana Lopez")).toBeInTheDocument();
    expect(screen.getByText("ana@example.com")).toBeInTheDocument();
    expect(screen.getByText(/the backend has no endpoint for it/)).toBeInTheDocument();
  });
});
