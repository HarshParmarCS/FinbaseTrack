import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountMenu } from "@/components/layout/account-menu";
import { AuthGate } from "@/features/auth/auth-gate";
import { GuestGate } from "@/features/auth/guest-gate";
import { setSessionExpiredHandler } from "@/lib/api/client";
import { api } from "@/lib/api/client";
import {
  clearCookie,
  errorBody,
  reply,
  setCookie,
  stubFetch,
  type FetchMock,
} from "../api/helpers";
import { ana, nav, renderWithAuth, resetNav } from "./utils";

vi.mock("next/navigation", async () => (await import("./utils")).mockNextNavigation());

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
  setSessionExpiredHandler(null);
});

const protectedPage = <AuthGate>protected content</AuthGate>;
const urls = () => fetchMock.mock.calls.map(([u]) => String(u));

describe("AuthGate", () => {
  it("sends a visitor without a session to the login page and keeps their destination", async () => {
    resetNav("/projects", "?q=a");

    renderWithAuth(protectedPage);

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/login?next=%2Fprojects%3Fq%3Da"),
    );
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled(); // no hint cookie, so nothing to ask the backend
  });

  it("shows a loading state, then the content, once the backend confirms the session", async () => {
    resetNav("/dashboard");
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async () => reply(200, { data: ana }));

    renderWithAuth(protectedPage);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByText("protected content")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("goes to login when the cookie hint is stale and the backend says 401", async () => {
    resetNav("/dashboard");
    setCookie("csrf_token", "stale");
    fetchMock.mockImplementation(async () => reply(401, errorBody("UNAUTHENTICATED", "no")));

    renderWithAuth(protectedPage);

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login?next=%2Fdashboard"));
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("shows a retryable error, not a login redirect, when the backend is unreachable", async () => {
    resetNav("/dashboard");
    setCookie("csrf_token", "t");
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();

    renderWithAuth(protectedPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot check your session");
    expect(nav.replace).not.toHaveBeenCalled();

    fetchMock.mockImplementation(async () => reply(200, { data: ana }));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("protected content")).toBeInTheDocument();
  });

  it("redirects with the expired reason when a refresh fails mid-session", async () => {
    resetNav("/projects");
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/me")
        ? reply(200, { data: ana })
        : reply(401, errorBody("UNAUTHENTICATED", "expired")),
    );
    renderWithAuth(protectedPage);
    await screen.findByText("protected content");

    await expect(api.get("/projects")).rejects.toMatchObject({ status: 401 });

    await waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith("/login?reason=expired&next=%2Fprojects"),
    );
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
    expect(urls().filter((u) => u.endsWith("/auth/refresh"))).toHaveLength(1);
  });
});

describe("GuestGate", () => {
  it("shows the form to a visitor", () => {
    resetNav("/login");

    renderWithAuth(<GuestGate>the form</GuestGate>);

    expect(screen.getByText("the form")).toBeInTheDocument();
  });

  it("moves a signed-in user on, to a safe next page only", async () => {
    resetNav("/login", "?next=https%3A%2F%2Fevil.example");
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async () => reply(200, { data: ana }));

    renderWithAuth(<GuestGate>the form</GuestGate>);

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("honors a safe next page", async () => {
    resetNav("/login", "?next=%2Fprojects");
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async () => reply(200, { data: ana }));

    renderWithAuth(<GuestGate>the form</GuestGate>);

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/projects"));
  });
});

describe("sign out", () => {
  async function renderSignedIn() {
    resetNav("/dashboard");
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/me") ? reply(200, { data: ana }) : reply(204),
    );
    const user = userEvent.setup();
    renderWithAuth(
      <AuthGate>
        <AccountMenu />
      </AuthGate>,
    );
    await user.click(await screen.findByRole("button", { name: "Account menu" }));
    return user;
  }

  it("shows who is signed in", async () => {
    await renderSignedIn();

    expect(screen.getByText("Ana Lopez")).toBeInTheDocument();
    expect(screen.getByText("ana@example.com")).toBeInTheDocument();
  });

  it("calls the real logout endpoint, then goes to a clean login page", async () => {
    const user = await renderSignedIn();

    await user.click(screen.getByRole("menuitem", { name: "Sign out" }));

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
    const logoutCall = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/auth/logout"));
    expect(logoutCall?.[1]?.method).toBe("POST");
    expect(new Headers(logoutCall?.[1]?.headers).get("x-csrf-token")).toBe("t");
  });

  it("stays signed in and says so when logout fails", async () => {
    const user = await renderSignedIn();
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/logout")
        ? reply(500, errorBody("INTERNAL_ERROR", "boom"))
        : reply(200, { data: ana }),
    );

    await user.click(screen.getByRole("menuitem", { name: "Sign out" }));

    expect(await screen.findByText(/Could not sign out/)).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });
});
