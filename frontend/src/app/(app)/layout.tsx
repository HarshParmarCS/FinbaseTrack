import { Suspense, type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { FullPageLoading } from "@/components/shared/full-page-status";
import { AuthGate } from "@/features/auth/auth-gate";

export default function AppLayout({ children }: { children: ReactNode }) {
  // The shell reads the current path (usePathname), which is request data on dynamic routes such
  // as /projects/[projectId], so Cache Components needs a Suspense boundary around it.
  return (
    <Suspense fallback={<FullPageLoading />}>
      <AuthGate>
        <AppShell>{children}</AppShell>
      </AuthGate>
    </Suspense>
  );
}
