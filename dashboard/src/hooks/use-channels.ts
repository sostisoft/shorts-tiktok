"use client";

import useSWR from "swr";
import type { APIEnvelope, ChannelResponse } from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useChannels() {
  const { data, error, isLoading, mutate } = useSWR<
    APIEnvelope<ChannelResponse[]>
  >("/api/channels", fetcher);

  return {
    channels: data?.data ?? [],
    isLoading,
    error,
    mutate,
  };
}
