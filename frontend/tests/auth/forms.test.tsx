import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/features/auth/login-form";
import { RegisterForm } from "@/features/auth/register-form";
import { authKeys } from "@/features/auth/keys";
import {
  callInit,
  callUrl,
  clearCookie,
  errorBody,
  reply,
  stubFetch,
  type FetchMock,
} from "../api/helpers";
import { ana, renderWithAuth, resetNav } from "./utils";

vi.mock("next/navigation", async () => (await import("./utils")).mockNextNavigation());

let fetchMock: FetchMock;

beforeEach(() => {
  resetNav("/login");
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

const posts = () => fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");

describe("LoginForm", () => {
  it("validates before sending anything", async () => {
    const user = userEvent.setup();
    renderWithAuth(<LoginForm />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your email address")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it("posts the credentials to the login endpoint and stores the user", async () => {
    fetchMock.mockImplementation(async () => reply(200, { data: ana }));
    const user = userEvent.setup();
    const { queryClient } = renderWithAuth(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(queryClient.getQueryData(authKeys.me())).toEqual(ana));
    expect(callUrl(fetchMock)).toBe("/api/v1/auth/login");
    expect(JSON.parse(String(callInit(fetchMock).body))).toEqual({
      email: "ana@example.com",
      password: "correct-horse-battery",
    });
  });

  it("shows the generic backend message for wrong credentials", async () => {
    fetchMock.mockImplementation(async () =>
      reply(401, errorBody("UNAUTHENTICATED", "Invalid email or password.")),
    );
    const user = userEvent.setup();
    renderWithAuth(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("puts a 422 field error on its field", async () => {
    fetchMock.mockImplementation(async () =>
      reply(
        422,
        errorBody("VALIDATION_ERROR", "Request validation failed.", {
          details: [{ field: "email", message: "Server says no", policy_id: null }],
        }),
      ),
    );
    const user = userEvent.setup();
    renderWithAuth(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Password"), "x");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Server says no")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("explains when the server cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    renderWithAuth(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Password"), "x");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("tells the user their session expired", () => {
    resetNav("/login", "?reason=expired&next=%2Fprojects");

    renderWithAuth(<LoginForm />);

    expect(screen.getByRole("status")).toHaveTextContent("Your session expired");
    expect(screen.getByRole("link", { name: "Create one" })).toHaveAttribute(
      "href",
      "/register?next=%2Fprojects",
    );
  });
});

describe("RegisterForm", () => {
  const fill = async (
    user: ReturnType<typeof userEvent.setup>,
    password = "correct-horse-battery",
  ) => {
    await user.type(screen.getByLabelText("Name"), "Ana Lopez");
    await user.type(screen.getByLabelText("Email"), "ana@example.com");
    await user.type(screen.getByLabelText("Password"), password);
  };

  it("enforces the backend's password length before sending", async () => {
    const user = userEvent.setup();
    renderWithAuth(<RegisterForm />);

    await fill(user, "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Use at least 8 characters")).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it("sends exactly name, email and password, then holds the new session", async () => {
    fetchMock.mockImplementation(async () => reply(201, { data: ana }));
    const user = userEvent.setup();
    const { queryClient } = renderWithAuth(<RegisterForm />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(queryClient.getQueryData(authKeys.me())).toEqual(ana));
    expect(callUrl(fetchMock)).toBe("/api/v1/auth/register");
    expect(JSON.parse(String(callInit(fetchMock).body))).toEqual({
      name: "Ana Lopez",
      email: "ana@example.com",
      password: "correct-horse-battery",
    });
  });

  it("shows a duplicate email on the email field", async () => {
    fetchMock.mockImplementation(async () =>
      reply(409, errorBody("CONFLICT", "An account with this email already exists.")),
    );
    const user = userEvent.setup();
    renderWithAuth(<RegisterForm />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("An account with this email already exists."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("maps backend 422 details to the matching fields", async () => {
    fetchMock.mockImplementation(async () =>
      reply(
        422,
        errorBody("VALIDATION_ERROR", "Request validation failed.", {
          details: [{ field: "password", message: "Too common", policy_id: null }],
        }),
      ),
    );
    const user = userEvent.setup();
    renderWithAuth(<RegisterForm />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Too common")).toBeInTheDocument();
  });
});
