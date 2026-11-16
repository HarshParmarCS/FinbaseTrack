"use client";

import { PageHeader } from "@/components/shared/page-header";
import { SectionCard } from "@/components/shared/section-card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/features/auth/auth-provider";
import { initials } from "@/lib/format";

/** The signed-in account as the backend reports it (GET /auth/me). Read-only: see the note. */
export function AccountView() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Account" title="Settings" description="Your account." />
      <SectionCard title="Account">
        <div className="flex items-center gap-4">
          <Avatar size="lg">
            <AvatarFallback className="bg-brand-gradient text-primary-foreground">
              {initials(user.name)}
            </AvatarFallback>
          </Avatar>
          <dl className="grid gap-1 text-sm">
            <div>
              <dt className="sr-only">Name</dt>
              <dd className="font-medium">{user.name}</dd>
            </div>
            <div>
              <dt className="sr-only">Email</dt>
              <dd className="text-muted-foreground">{user.email}</dd>
            </div>
          </dl>
        </div>
        <p className="text-xs text-muted-foreground">
          Changing your name, email or password is not available: the backend has no endpoint for it
          yet.
        </p>
      </SectionCard>
    </div>
  );
}
