"use client";

import useSWR from "swr";
import type { APIEnvelope, VideoResponse } from "@/lib/types";
import { PROCESSING_STATUSES } from "@/lib/constants";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useVideos(page = 1, limit = 20, status?: string) {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });
  if (status) params.set("status", status);

  const { data, error, isLoading, mutate } = useSWR<
    APIEnvelope<VideoResponse[]>
  >(`/api/videos?${params}`, fetcher, {
    refreshInterval: 10000,
  });

  return {
    videos: data?.data ?? [],
    meta: data?.meta ?? null,
    isLoading,
    error,
    mutate,
  };
}

export function useVideo(id: string) {
  const { data, error, isLoading, mutate } = useSWR<
    APIEnvelope<VideoResponse>
  >(`/api/videos/${id}`, fetcher, {
    refreshInterval: (latestData) => {
      const status = latestData?.data?.status;
      if (status && PROCESSING_STATUSES.includes(status)) return 5000;
      return 0;
    },
  });

  return {
    video: data?.data ?? null,
    isLoading,
    error,
    mutate,
  };
}
