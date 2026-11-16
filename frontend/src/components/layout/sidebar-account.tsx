"use client";

import { Loader2, LogOut } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-provider";
import { initials } from "@/lib/format";

/**
 * The signed-in user and the sign-out button, at the bottom of the sidebar (desktop and mobile).
 * Signing out calls the real backend (POST /auth/logout) through useAuth().signOut(); on success
 * AuthGate sends the user to /login. On failure the user stays signed in and is told why.
 */
export function SidebarAccount() {
  const { user, signOut } = useAuth();
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!user) return null;

  async function handleSignOut() {
    setFailed(false);
    setPending(true);
    const ok = await signOut();
    setPending(false);
    if (ok) toast.success("You are signed out");
    else setFailed(true);
  }

  return (
    <div className="space-y-3 rounded-2xl border border-sidebar-border bg-brand-50/60 p-3">
      <div className="flex items-center gap-3">
        <Avatar>
          <AvatarFallback className="bg-brand-gradient text-xs font-semibold text-primary-foreground">
            {initials(user.name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{user.name}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </div>
      </div>
      <Button
        variant="outline"
        className="w-full justify-center"
        onClick={() => void handleSignOut()}
        disabled={pending}
      >
        {pending ? <Loader2 className="animate-spin" aria-hidden /> : <LogOut aria-hidden />}
        {pending ? "Signing out…" : "Sign out"}
      </Button>
      {failed ? (
        <p role="alert" className="text-xs text-danger">
          Could not sign out. Check your connection and try again.
        </p>
      ) : null}
    </div>
  );
}
