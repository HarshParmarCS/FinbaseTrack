import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Envelope, LoginIn, RegisterIn, UserOut } from "@/types/api";

export async function register(input: RegisterIn): Promise<UserOut> {
  return (await api.post<Envelope<UserOut>>(endpoints.auth.register, input)).data;
}

export async function login(input: LoginIn): Promise<UserOut> {
  return (await api.post<Envelope<UserOut>>(endpoints.auth.login, input)).data;
}

export async function logout(): Promise<void> {
  await api.post<void>(endpoints.auth.logout);
}

export async function getCurrentUser(signal?: AbortSignal): Promise<UserOut> {
  return (await api.get<Envelope<UserOut>>(endpoints.auth.me, { signal })).data;
}
