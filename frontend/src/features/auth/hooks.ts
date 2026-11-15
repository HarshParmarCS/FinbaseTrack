"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { login, logout, register } from "@/features/auth/api";
import { authKeys } from "@/features/auth/keys";
import { fetchSession, resetUserData } from "@/features/auth/session";
import type { UserOut } from "@/types/api";

/** `null` data means "no session"; an error means the backend could not be asked. */
export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.me(),
    queryFn: ({ signal }) => fetchSession(signal),
    retry: false,
  });
}

function useStartSession() {
  const queryClient = useQueryClient();
  return (user: UserOut) => {
    resetUserData(queryClient);
    queryClient.setQueryData(authKeys.me(), user);
  };
}

export function useLogin() {
  return useMutation({ mutationFn: login, onSuccess: useStartSession() });
}

export function useRegister() {
  return useMutation({ mutationFn: register, onSuccess: useStartSession() });
}

export function useLogout() {
  return useMutation({ mutationFn: logout });
}
