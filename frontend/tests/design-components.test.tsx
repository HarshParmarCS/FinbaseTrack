import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Eyebrow } from "@/components/shared/eyebrow";
import { IconTile } from "@/components/shared/icon-tile";
import { InputWithIcon } from "@/components/shared/input-with-icon";
import { PasswordInput } from "@/components/shared/password-input";
import { PillTab, PillTabs } from "@/components/shared/pill-tabs";
import { SectionCard } from "@/components/shared/section-card";
import { StatCard } from "@/components/shared/stat-card";
import { Button } from "@/components/ui/button";
import { TaskPriorityBadge, TaskStatusBadge } from "@/features/tasks/badges";

describe("PasswordInput", () => {
  it("hides the password, shows it on request and hides it again", async () => {
    const user = userEvent.setup();
    render(
      <>
        <label htmlFor="pw">Password</label>
        <PasswordInput id="pw" defaultValue="s3cret-value" />
      </>,
    );
    const field = screen.getByLabelText("Password");
    const toggle = screen.getByRole("button", { name: "Show password" });

    expect(field).toHaveAttribute("type", "password");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveAttribute("aria-controls", "pw");

    await user.click(toggle);
    expect(field).toHaveAttribute("type", "text");
    expect(toggle).toHaveAttribute("aria-pressed", "true");

    await user.click(toggle);
    expect(field).toHaveAttribute("type", "password");
  });

  it("keeps the focus in the field when the toggle is clicked, and works from the keyboard", async () => {
    const user = userEvent.setup();
    render(<PasswordInput id="pw" aria-label="Password" />);
    const field = screen.getByLabelText("Password");

    await user.click(field);
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(field).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("button", { name: "Show password" })).toHaveFocus();
    expect(field).toHaveAttribute("type", "text"); // shown by the click above
    await user.keyboard("{Enter}");
    expect(field).toHaveAttribute("type", "password");
  });

  it("passes the ref and change handler through (React Hook Form register)", async () => {
    const user = userEvent.setup();
    const ref = { current: null as HTMLInputElement | null };
    const onChange = vi.fn();
    render(<PasswordInput aria-label="Password" ref={ref} onChange={onChange} />);

    await user.type(screen.getByLabelText("Password"), "abc");

    expect(ref.current).toBeInstanceOf(HTMLInputElement);
    expect(onChange).toHaveBeenCalledTimes(3);
  });
});

describe("InputWithIcon", () => {
  it("is a normal labelled input with a decorative icon", () => {
    render(<InputWithIcon icon={Inbox} aria-label="Email" type="email" />);

    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
    expect(document.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("PillTabs", () => {
  function Example() {
    const [on, setOn] = useState<string[]>(["todo"]);
    const toggle = (value: string) =>
      setOn((list) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]));
    return (
      <PillTabs label="Status">
        {["todo", "done"].map((value) => (
          <PillTab key={value} pressed={on.includes(value)} onClick={() => toggle(value)}>
            {value}
          </PillTab>
        ))}
      </PillTabs>
    );
  }

  it("groups the pills under a label and reports the pressed state", async () => {
    const user = userEvent.setup();
    render(<Example />);

    expect(screen.getByRole("group", { name: "Status" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "todo" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "done" }));
    expect(screen.getByRole("button", { name: "done" })).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles with Space and Enter from the keyboard", async () => {
    const user = userEvent.setup();
    render(<Example />);

    screen.getByRole("button", { name: "todo" }).focus();
    await user.keyboard(" ");
    expect(screen.getByRole("button", { name: "todo" })).toHaveAttribute("aria-pressed", "false");
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "todo" })).toHaveAttribute("aria-pressed", "true");
  });

  it("marks the active pill with the highlight ring token", () => {
    render(<Example />);

    expect(screen.getByRole("button", { name: "todo" }).className).toContain("ring-highlight-ring");
    expect(screen.getByRole("button", { name: "done" }).className).not.toContain(
      "ring-highlight-ring",
    );
  });
});

describe("StatCard", () => {
  it("shows the label and value together, and a hint", () => {
    render(<StatCard label="Total tasks" icon={Inbox} value={12} hint="All projects" />);

    expect(screen.getByText("Total tasks").parentElement).toHaveTextContent(
      "Total tasks12All projects",
    );
  });

  it("shows a skeleton and no value or hint while loading", () => {
    const { container } = render(
      <StatCard label="Total tasks" icon={Inbox} value={5} hint="All" isLoading />,
    );

    expect(screen.queryByText("5")).not.toBeInTheDocument();
    expect(screen.queryByText("All")).not.toBeInTheDocument();
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });
});

describe("brand pieces", () => {
  it("IconTile is decorative and uses the tone's tokens", () => {
    const { container } = render(<IconTile icon={Inbox} tone="success" />);
    const tile = container.firstElementChild as HTMLElement;

    expect(tile).toHaveAttribute("aria-hidden", "true");
    expect(tile.className).toContain("bg-success-soft");
  });

  it("Eyebrow and SectionCard render the label above the title", () => {
    render(
      <SectionCard title="Members" eyebrow="Team">
        body
      </SectionCard>,
    );

    expect(screen.getByText("Team")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Members" })).toBeInTheDocument();
    render(<Eyebrow>Capabilities</Eyebrow>);
    expect(screen.getByText("Capabilities")).toBeInTheDocument();
  });

  it("the primary button uses the brand gradient and the CTA size is uppercase", () => {
    render(
      <>
        <Button>Save</Button>
        <Button size="cta">Sign in</Button>
      </>,
    );

    expect(screen.getByRole("button", { name: "Save" }).className).toContain("bg-brand-gradient");
    expect(screen.getByRole("button", { name: "Sign in" }).className).toContain("uppercase");
  });

  it("task badges take their colors from the status and priority tokens", () => {
    render(
      <>
        <TaskStatusBadge status="completed" />
        <TaskPriorityBadge priority="high" />
      </>,
    );

    expect(screen.getByText("Completed").className).toContain("bg-status-completed-soft");
    expect(screen.getByText("High").className).toContain("text-priority-high");
  });
});
