import type { Metadata } from "next";
import { Brand } from "@/components/layout/brand";
import { PageHeader } from "@/components/shared/page-header";
import { DiagnosticsPanel } from "@/features/diagnostics/diagnostics-panel";

export const metadata: Metadata = { title: "API diagnostics" };

// Public on purpose: it must work while signed out (a 401 from /auth/me is a healthy answer).
export default function DiagnosticsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl space-y-6 px-4 py-10">
      <Brand href="/login" />
      <PageHeader
        eyebrow="System"
        title="API diagnostics"
        description="Checks that this app can talk to the running backend. It uses no sample data."
      />
      <DiagnosticsPanel />
    </main>
  );
}
