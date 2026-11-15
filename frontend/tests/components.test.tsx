import { render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { EmptyState } from "@/components/shared/empty-state";
import { StatCard } from "@/components/shared/stat-card";

const navigation = vi.hoisted(() => ({ pathname: "/projects/42" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname }));

describe("SidebarNav", () => {
  it("marks the section containing the current path as the current page", () => {
    render(<SidebarNav />);

    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("links every section", () => {
    render(<SidebarNav />);

    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(screen.getByRole("link", { name: "My Tasks" })).toHaveAttribute("href", "/my-tasks");
  });
});

describe("EmptyState", () => {
  it("shows its title and description", () => {
    render(<EmptyState icon={Inbox} title="Nothing here" description="Add something first." />);

    expect(screen.getByRole("heading", { name: "Nothing here" })).toBeInTheDocument();
    expect(screen.getByText("Add something first.")).toBeInTheDocument();
  });
});

describe("StatCard", () => {
  it("shows a dash when no value is loaded", () => {
    render(<StatCard label="Total tasks" icon={Inbox} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows the value, including zero", () => {
    render(<StatCard label="Total tasks" icon={Inbox} value={0} />);

    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("hides the value while loading", () => {
    render(<StatCard label="Total tasks" icon={Inbox} value={5} isLoading />);

    expect(screen.queryByText("5")).not.toBeInTheDocument();
  });
});
