import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Brand } from "@/components/layout/brand";
import { GuestGate } from "@/features/auth/guest-gate";

const FOR_TEAMS = ["Projects", "Tasks", "Teams"];

/**
 * Split sign-in layout from the Finbase reference: a violet brand panel on the left (from `lg`
 * up) and the form on the right. Below `lg` only the form shows, with the mark above it.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <aside
        aria-label="About Finbase Workdesk"
        className="relative hidden flex-col justify-between overflow-hidden p-12 text-primary-foreground bg-brand-panel lg:flex xl:p-16"
      >
        <div className="w-fit rounded-2xl bg-card px-4 py-3 shadow-glow">
          <Brand href="/login" />
        </div>
        <div className="max-w-xl space-y-6">
          <h2 className="text-5xl leading-[1.05] font-bold tracking-tight xl:text-6xl">
            Plan, assign and deliver work, together.
          </h2>
          <p className="max-w-md text-lg text-brand-200">
            Projects, tasks and your team&apos;s activity in one secure workspace, with access
            decided by clear policies.
          </p>
        </div>
        <div className="space-y-4 border-t border-primary-foreground/15 pt-8">
          <p className="text-xs font-semibold tracking-[0.35em] text-brand-300 uppercase">
            Built for project teams
          </p>
          <ul className="flex flex-wrap gap-x-8 gap-y-2 text-lg font-bold text-brand-200 uppercase">
            {FOR_TEAMS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex flex-col items-center justify-center bg-card px-6 py-12 sm:px-10">
        <div className="w-full max-w-md space-y-10">
          <div className="lg:hidden">
            <Brand href="/login" />
          </div>
          <GuestGate>{children}</GuestGate>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-4 text-brand-400" aria-hidden />
            Your session is kept in secure, HttpOnly cookies.
          </p>
        </div>
      </main>
    </div>
  );
}
