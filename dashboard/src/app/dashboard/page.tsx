"use client";

import Link from "next/link";
import { Plus, Video, BarChart3 } from "lucide-react";
import { useVideos } from "@/hooks/use-videos";
import { useUsage } from "@/hooks/use-usage";
import { UsageProgressBar } from "@/components/usage/usage-progress-bar";
import { VideoGrid } from "@/components/videos/video-grid";

export default function DashboardOverview() {
  const { videos, isLoading: videosLoading } = useVideos(1, 6);
  const { usage, isLoading: usageLoading } = useUsage();

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Link
          href="/dashboard/videos/new"
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Video
        </Link>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        {usage && <UsageProgressBar usage={usage} />}

        <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
            <Video className="h-5 w-5 text-green-700" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {usageLoading ? "-" : usage?.videos_published ?? 0}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">Published</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
            <BarChart3 className="h-5 w-5 text-blue-700" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {usageLoading
                ? "-"
                : `$${(usage?.api_cost_usd ?? 0).toFixed(2)}`}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">
              API Cost (month)
            </p>
          </div>
        </div>
      </div>

      {/* Recent videos */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Videos</h2>
          <Link
            href="/dashboard/videos"
            className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            View all
          </Link>
        </div>
        {videosLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-52 animate-pulse rounded-xl bg-[var(--muted)]"
              />
            ))}
          </div>
        ) : (
          <VideoGrid videos={videos} />
        )}
      </div>
    </div>
  );
}
