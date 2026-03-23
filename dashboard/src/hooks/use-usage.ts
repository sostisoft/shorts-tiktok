"use client";

import useSWR from "swr";
import type { APIEnvelope, UsageResponse } from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useUsage() {
  const { data, error, isLoading } = useSWR<APIEnvelope<UsageResponse>>(
    "/api/usage",
    fetcher,
    { refreshInterval: 60000 },
  );

  return {
    usage: data?.data ?? null,
    isLoading,
    error,
  };
}
