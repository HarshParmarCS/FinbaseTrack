import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  // sonner keeps toasts in a module-level store; do not let one test's toasts reach the next.
  toast.dismiss();
});
