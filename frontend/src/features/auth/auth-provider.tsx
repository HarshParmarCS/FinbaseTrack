"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authKeys } from "@/features/auth/keys";
import { useCurrentUser, useLogout } from "@/features/auth/hooks";
import type { SessionEnd } from "@/features/auth/redirect";
import { resetUserData } from "@/features/auth/session";
import { clearCsrfCookie, setSessionExpiredHandler } from "@/lib/api/client";
import type { UserOut } from "@/types/api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "error";

type AuthContextValue = {
  status: AuthStatus;
  user: UserOut | null;
  /** Why the last session ended; null for a visitor who never signed in. */
  endedBy: SessionEnd;
  /** Ask the backend again (after a network error). */
  retry: () => void;
  /** Calls the backend logout endpoint. Resolves false if it failed (session may still exist). */
  signOut: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const session = useCurrentUser();
  const logout = useLogout();
  const [endedByState, setEndedBy] = useState<SessionEnd>(null);

  const user = session.data ?? null;
  const refetch = session.refetch;

  // The API client reports when a refresh failed: the session is over. Only a user who WAS signed
  // in sees "expired"; a first visit without a session is just a visitor.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      if (!queryClient.getQueryData(authKeys.me())) return;
      resetUserData(queryClient);
      queryClient.setQueryData(authKeys.me(), null);
      setEndedBy("expired");
    });
    return () => setSessionExpiredHandler(null);
  }, [queryClient]);

  const signOut = useCallback(async () => {
    try {
      await logout.mutateAsync();
    } catch {
      return false;
    }
    clearCsrfCookie();
    resetUserData(queryClient);
    queryClient.setQueryData(authKeys.me(), null);
    setEndedBy("signed-out");
    return true;
  }, [logout, queryClient]);

  const value = useMemo<AuthContextValue>(() => {
    let status: AuthStatus = "unauthenticated";
    if (session.isPending) status = "loading";
    else if (session.isError) status = "error";
    else if (user) status = "authenticated";
    return {
      status,
      user,
      endedBy: user ? null : endedByState,
      retry: () => void refetch(),
      signOut,
    };
  }, [session.isPending, session.isError, user, endedByState, refetch, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
