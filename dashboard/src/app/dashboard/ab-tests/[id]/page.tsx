"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, Trophy, Loader2 } from "lucide-react";
import { VideoStatusBadge } from "@/components/videos/video-status-badge";
import type { APIEnvelope, VideoStatus } from "@/lib/types";

interface ABTestDetail {
  id: string;
  name: string;
  topic: string;
  template_a: string;
  template_b: string;
  status: string;
  winner: string | null;
  video_a: { id: string; title: string | null; status: VideoStatus } | null;
  video_b: { id: string; title: string | null; status: VideoStatus } | null;
  analytics_a: { views: number; likes: number; click_through_rate: number | null; avg_view_percentage: number | null } | null;
  analytics_b: { views: number; likes: number; click_through_rate: number | null; avg_view_percentage: number | null } | null;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function ABTestDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, mutate } = useSWR<APIEnvelope<ABTestDetail>>(`/api/ab-tests/${id}`, fetcher, { refreshInterval: 10000 });
  const test = data?.data;
  const [evaluating, setEvaluating] = useState(false);
  const router = useRouter();

  async function handleEvaluate() {
    setEvaluating(true);
    await fetch(`/api/ab-tests/${id}/evaluate`, { method: "POST" });
    mutate();
    setEvaluating(false);
  }

  if (isLoading) return <div className="h-64 animate-pulse rounded-xl bg-[var(--muted)]" />;
  if (!test) return <div className="py-16 text-center text-[var(--muted-foreground)]">Test not found</div>;

  const variants = [
    { label: "A", template: test.template_a, video: test.video_a, analytics: test.analytics_a, isWinner: test.winner === "a" },
    { label: "B", template: test.template_b, video: test.video_b, analytics: test.analytics_b, isWinner: test.winner === "b" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.push("/dashboard/ab-tests")} className="rounded-lg p-1.5 hover:bg-[var(--accent)]">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold">{test.name}</h1>
          <p className="text-xs text-[var(--muted-foreground)]">{test.topic}</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {variants.map((v) => (
          <div key={v.label} className={`rounded-xl border-2 p-4 ${v.isWinner ? "border-green-500" : "border-[var(--border)]"}`}>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold">Variant {v.label}</h2>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs capitalize">{v.template}</span>
                {v.isWinner && <Trophy className="h-5 w-5 text-yellow-500" />}
              </div>
            </div>

            {v.video ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>{v.video.title || "Untitled"}</span>
                  <VideoStatusBadge status={v.video.status} />
                </div>

                {v.analytics ? (
                  <div className="grid grid-cols-2 gap-2 rounded-lg bg-[var(--muted)] p-3 text-sm">
                    <div><span className="text-[var(--muted-foreground)]">Views:</span> <strong>{v.analytics.views.toLocaleString()}</strong></div>
                    <div><span className="text-[var(--muted-foreground)]">Likes:</span> <strong>{v.analytics.likes}</strong></div>
                    <div><span className="text-[var(--muted-foreground)]">CTR:</span> <strong>{v.analytics.click_through_rate ? `${(v.analytics.click_through_rate * 100).toFixed(1)}%` : "—"}</strong></div>
                    <div><span className="text-[var(--muted-foreground)]">Retention:</span> <strong>{v.analytics.avg_view_percentage ? `${v.analytics.avg_view_percentage.toFixed(0)}%` : "—"}</strong></div>
                  </div>
                ) : (
                  <p className="text-xs text-[var(--muted-foreground)]">No analytics yet</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--muted-foreground)]">Video not created</p>
            )}
          </div>
        ))}
      </div>

      {test.status === "running" && (
        <button
          onClick={handleEvaluate} disabled={evaluating}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
        >
          {evaluating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trophy className="h-4 w-4" />}
          {evaluating ? "Evaluating..." : "Evaluate Winner"}
        </button>
      )}

      {test.winner && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-center dark:border-green-800 dark:bg-green-950">
          <Trophy className="mx-auto mb-2 h-8 w-8 text-yellow-500" />
          <p className="font-bold text-green-800 dark:text-green-200">
            Winner: Variant {test.winner.toUpperCase()} ({test.winner === "a" ? test.template_a : test.template_b})
          </p>
        </div>
      )}
    </div>
  );
}
