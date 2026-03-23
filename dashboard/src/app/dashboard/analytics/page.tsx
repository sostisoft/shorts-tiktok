"use client";

import useSWR from "swr";
import { TrendingUp, Eye, Heart, MessageSquare, Trophy } from "lucide-react";
import type { APIEnvelope } from "@/lib/types";

interface AnalyticsSummary {
  total_views: number;
  total_likes: number;
  total_comments: number;
  avg_ctr: number | null;
  avg_retention: number | null;
  best_video_id: string | null;
  best_video_title: string | null;
  best_video_views: number;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function AnalyticsPage() {
  const { data, isLoading } = useSWR<APIEnvelope<AnalyticsSummary>>("/api/analytics/summary", fetcher, { refreshInterval: 60000 });
  const summary = data?.data;

  const stats = [
    { label: "Total Views", value: summary?.total_views ?? 0, icon: Eye, bg: "bg-blue-100", fg: "text-blue-700" },
    { label: "Total Likes", value: summary?.total_likes ?? 0, icon: Heart, bg: "bg-red-100", fg: "text-red-700" },
    { label: "Total Comments", value: summary?.total_comments ?? 0, icon: MessageSquare, bg: "bg-green-100", fg: "text-green-700" },
    { label: "Avg CTR", value: summary?.avg_ctr ? `${(summary.avg_ctr * 100).toFixed(1)}%` : "—", icon: TrendingUp, bg: "bg-purple-100", fg: "text-purple-700" },
    { label: "Avg Retention", value: summary?.avg_retention ? `${summary.avg_retention.toFixed(0)}%` : "—", icon: TrendingUp, bg: "bg-yellow-100", fg: "text-yellow-700" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Analytics</h1>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[1, 2, 3, 4, 5].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-[var(--muted)]" />)}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {stats.map((s) => (
              <div key={s.label} className="rounded-xl border border-[var(--border)] p-4">
                <div className="flex items-center gap-2">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${s.bg}`}>
                    <s.icon className={`h-4 w-4 ${s.fg}`} />
                  </div>
                  <span className="text-xs text-[var(--muted-foreground)]">{s.label}</span>
                </div>
                <p className="mt-2 text-2xl font-bold">{typeof s.value === "number" ? s.value.toLocaleString() : s.value}</p>
              </div>
            ))}
          </div>

          {summary?.best_video_id && (
            <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] p-4">
              <Trophy className="h-6 w-6 text-yellow-500" />
              <div>
                <p className="text-sm font-medium">Best Performing Video</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {summary.best_video_title || "Untitled"} — {summary.best_video_views.toLocaleString()} views
                </p>
              </div>
            </div>
          )}

          {!summary?.total_views && (
            <div className="rounded-xl border border-dashed border-[var(--border)] py-16 text-center">
              <TrendingUp className="mx-auto mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
              <p className="text-sm text-[var(--muted-foreground)]">
                No analytics data yet. Publish videos to YouTube and analytics will appear here.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
