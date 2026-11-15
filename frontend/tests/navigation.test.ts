import { describe, expect, it } from "vitest";
import { NAV_ITEMS, findNavItem, isActivePath } from "@/config/navigation";

describe("navigation", () => {
  it("lists the five sections in order", () => {
    expect(NAV_ITEMS.map((item) => item.label)).toEqual([
      "Dashboard",
      "My Tasks",
      "Projects",
      "Activity",
      "Settings",
    ]);
  });

  it("matches nested paths but not look-alike prefixes", () => {
    expect(isActivePath("/projects/abc/tasks/1", "/projects")).toBe(true);
    expect(isActivePath("/projects-archive", "/projects")).toBe(false);
  });

  it("finds the current item for a path", () => {
    expect(findNavItem("/my-tasks")?.label).toBe("My Tasks");
    expect(findNavItem("/nowhere")).toBeUndefined();
  });
});
