import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuthLayout from "@/app/(auth)/layout";
import { Brand } from "@/components/layout/brand";
import { LoginForm } from "@/features/auth/login-form";
import { RegisterForm } from "@/features/auth/register-form";
import { stubFetch } from "./api/helpers";
import { renderWithAuth, resetNav } from "./auth/utils";

vi.mock("next/navigation", async () => (await import("./auth/utils")).mockNextNavigation());

beforeEach(() => {
  resetNav("/login");
  stubFetch();
});

afterEach(() => vi.unstubAllGlobals());

describe("Brand", () => {
  it("shows the configured product name and links home", () => {
    renderWithAuth(<Brand />);

    const link = screen.getByRole("link", { name: "Finbase Workdesk home" });
    expect(link).toHaveAttribute("href", "/dashboard");
    expect(link).toHaveTextContent("Finbase Workdesk");
    expect(link.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("split sign-in layout", () => {
  it("has the brand panel, the headline and the form", () => {
    renderWithAuth(
      <AuthLayout>
        <LoginForm />
      </AuthLayout>,
    );

    const panel = screen.getByRole("complementary", { name: "About Finbase Workdesk" });
    expect(
      within(panel).getByRole("heading", { name: /Plan, assign and deliver work/ }),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Built for project teams")).toBeInTheDocument();
    expect(screen.getByRole("main")).toContainElement(
      screen.getByRole("form", { name: "Sign in" }),
    );
  });

  it("offers no controls the backend cannot support", () => {
    renderWithAuth(
      <AuthLayout>
        <LoginForm />
      </AuthLayout>,
    );

    expect(screen.queryByText(/forgot password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/trust this device/i)).not.toBeInTheDocument();
  });
});

describe("sign-in and register fields", () => {
  it("lets the user reveal the password, and the button keeps its name", async () => {
    const user = userEvent.setup();
    renderWithAuth(<LoginForm />);
    const password = screen.getByLabelText("Password");

    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Sign in" }).className).toContain("uppercase");
  });

  it("register has name, email and password fields with the same labels", () => {
    renderWithAuth(<RegisterForm />);

    expect(screen.getByLabelText("Name")).toHaveAttribute("autocomplete", "name");
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });
});
