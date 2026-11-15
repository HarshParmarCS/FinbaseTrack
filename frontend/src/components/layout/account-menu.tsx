"use client";

import { LogOut } from "lucide-react";
import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { initials } from "@/lib/format";
import { useAuth } from "@/features/auth/auth-provider";
import { toast } from "sonner";

export function AccountMenu() {
  const { user, signOut } = useAuth();
  const [failed, setFailed] = useState(false);

  async function handleSignOut() {
    setFailed(false);
    if (await signOut()) toast.success("You are signed out");
    else setFailed(true);
  }

  if (!user) return null;

  return (
    <DropdownMenu onOpenChange={(open) => open && setFailed(false)}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label="Account menu">
          <Avatar size="sm">
            <AvatarFallback>{initials(user.name)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="space-y-0.5 font-normal">
          <p className="text-sm font-medium">{user.name}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {failed ? (
          <p role="alert" className="px-2 py-1.5 text-xs text-destructive">
            Could not sign out. Check your connection and try again.
          </p>
        ) : null}
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault();
            void handleSignOut();
          }}
        >
          <LogOut aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
