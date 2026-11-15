import type { ReactNode } from "react";
import { Brand } from "@/components/layout/brand";
import { GuestGate } from "@/features/auth/guest-gate";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-4 py-10">
      <Brand />
      <div className="w-full max-w-sm">
        <GuestGate>{children}</GuestGate>
      </div>
    </main>
  );
}
