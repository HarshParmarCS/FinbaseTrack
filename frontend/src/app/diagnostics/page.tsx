import type { Metadata } from "next";
import { PageHeader } from "@/components/shared/page-header";
import { DiagnosticsPanel } from "@/features/diagnostics/diagnostics-panel";

export const metadata: Metadata = { title: "API diagnostics" };

// Public on purpose: it must work while signed out (a 401 from /auth/me is a healthy answer).
export default function DiagnosticsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-10">
      <PageHeader
        title="API diagnostics"
        description="Checks that this app can talk to the running backend. It uses no sample data."
      />
      <DiagnosticsPanel />
    </main>
  );
}
