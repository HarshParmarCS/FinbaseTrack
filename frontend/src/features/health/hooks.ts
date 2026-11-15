"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/features/health/api";
import { healthKeys } from "@/features/health/keys";

export function useHealth() {
  return useQuery({ queryKey: healthKeys.all, queryFn: ({ signal }) => getHealth(signal) });
}
