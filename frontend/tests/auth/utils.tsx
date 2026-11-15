import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";
import { AuthProvider } from "@/features/auth/auth-provider";
import { setSessionExpiredHandler } from "@/lib/api/client";

// Shared with the next/navigation mock, which each test file registers with a dynamic import.
export const nav = { replace: vi.fn(), pathname: "/dashboard", search: "" };

export function mockNextNavigation() {
  return {
    useRouter: () => ({ replace: nav.replace, push: nav.replace }),
    usePathname: () => nav.pathname,
    useSearchParams: () => new URLSearchParams(nav.search),
  };
}

export function resetNav(pathname = "/dashboard", search = "") {
  nav.replace.mockReset();
  nav.pathname = pathname;
  nav.search = search;
  window.history.replaceState(null, "", `${pathname}${search}`);
  setSessionExpiredHandler(null);
}

export function renderWithAuth(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

export const ana = { id: "u1", email: "ana@example.com", name: "Ana Lopez" };
