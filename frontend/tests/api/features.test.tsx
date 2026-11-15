import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { logout } from "@/features/auth/api";
import { dashboardKeys } from "@/features/dashboard/keys";
import { addMember, deleteProject, listMembers } from "@/features/projects/api";
import { projectKeys } from "@/features/projects/keys";
import { changeTaskStatus, createTask, listTasks } from "@/features/tasks/api";
import { useChangeTaskStatus } from "@/features/tasks/hooks";
import { taskKeys } from "@/features/tasks/keys";
import { callInit, callUrl, reply, stubFetch, type FetchMock } from "./helpers";

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = stubFetch();
});

afterEach(() => vi.unstubAllGlobals());

const user = { id: "u1", email: "a@b.co", name: "A" };

describe("feature API functions", () => {
  it("createTask posts to the project and unwraps data", async () => {
    fetchMock.mockResolvedValue(reply(201, { data: { id: "t1", title: "X" } }));

    const task = await createTask("p1", { title: "X" });

    expect(callUrl(fetchMock)).toBe("/api/v1/projects/p1/tasks");
    expect(callInit(fetchMock).method).toBe("POST");
    expect(task).toMatchObject({ id: "t1" });
  });

  it("changeTaskStatus patches the dedicated status endpoint", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: { id: "t1", status: "in_progress" } }));

    await changeTaskStatus("t1", { status: "in_progress", position: 512.5 });

    expect(callUrl(fetchMock)).toBe("/api/v1/tasks/t1/status");
    expect(callInit(fetchMock).method).toBe("PATCH");
    expect(callInit(fetchMock).body).toBe('{"status":"in_progress","position":512.5}');
  });

  it("listTasks keeps the paged envelope and repeats array filters", async () => {
    const page = { data: [], meta: { page: 1, page_size: 20, total: 0, total_pages: 0 } };
    fetchMock.mockResolvedValue(reply(200, page));

    const result = await listTasks("p1", { status: ["todo", "completed"], sort: "-due_date" });

    expect(callUrl(fetchMock)).toBe(
      "/api/v1/projects/p1/tasks?status=todo&status=completed&sort=-due_date",
    );
    expect(result).toEqual(page);
  });

  it("listMembers returns the plain array (the member list is not paged)", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: [{ user, is_owner: true, joined_at: "x" }] }));

    await expect(listMembers("p1")).resolves.toHaveLength(1);
  });

  it("addMember sends exactly the identifier given", async () => {
    fetchMock.mockResolvedValue(reply(201, { data: { user, is_owner: false, joined_at: "x" } }));

    await addMember("p1", { email: "ben@example.com" });

    expect(callInit(fetchMock).body).toBe('{"email":"ben@example.com"}');
  });

  it("deleteProject and logout resolve to undefined on 204", async () => {
    fetchMock.mockImplementation(async () => reply(204));

    await expect(deleteProject("p1")).resolves.toBeUndefined();
    await expect(logout()).resolves.toBeUndefined();
    expect(callUrl(fetchMock, 0)).toBe("/api/v1/projects/p1");
    expect(callUrl(fetchMock, 1)).toBe("/api/v1/auth/logout");
  });

  it("encodes path ids", async () => {
    fetchMock.mockResolvedValue(reply(204));

    await deleteProject("a/b");

    expect(callUrl(fetchMock)).toBe("/api/v1/projects/a%2Fb");
  });
});

describe("mutation hooks", () => {
  it("a status change refreshes task, project and dashboard data", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: { id: "t1", status: "completed" } }));
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useChangeTaskStatus("t1"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ status: "completed" });
    });

    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(4));
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(taskKeys.all);
    expect(keys).toContainEqual(projectKeys.all);
    expect(keys).toContainEqual(dashboardKeys.all);
  });
});
