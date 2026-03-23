"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Download, Trash2, Send, AlertCircle } from "lucide-react";
import { useVideo } from "@/hooks/use-videos";
import { VideoStatusBadge } from "@/components/videos/video-status-badge";
import { PipelineProgress } from "@/components/videos/pipeline-progress";
import { useState } from "react";

export default function VideoDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { video, isLoading, mutate } = useVideo(id);
  const [deleting, setDeleting] = useState(false);
  const router = useRouter();

  async function handleDelete() {
    if (!confirm("Delete this video permanently?")) return;
    setDeleting(true);
    await fetch(`/api/videos/${id}`, { method: "DELETE" });
    router.push("/dashboard/videos");
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--muted)]" />
        <div className="h-64 animate-pulse rounded-xl bg-[var(--muted)]" />
      </div>
    );
  }

  if (!video) {
    return (
      <div className="py-16 text-center">
        <p className="text-[var(--muted-foreground)]">Video not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/dashboard/videos")}
          className="rounded-lg p-1.5 hover:bg-[var(--accent)]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">
            {video.title || "Untitled Video"}
          </h1>
          <p className="text-xs text-[var(--muted-foreground)]">
            Job: {video.job_id}
          </p>
        </div>
        <VideoStatusBadge status={video.status} />
      </div>

      {/* Pipeline progress */}
      <div className="rounded-xl border border-[var(--border)] p-4">
        <h2 className="mb-3 text-sm font-medium">Pipeline Progress</h2>
        <PipelineProgress status={video.status} />
      </div>

      {/* Error message */}
      {video.status === "error" && video.error_message && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-200">
              Error
            </p>
            <p className="mt-1 text-sm text-red-700 dark:text-red-300">
              {video.error_message}
            </p>
          </div>
        </div>
      )}

      {/* Video player */}
      {video.video_url && (
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <video
            src={video.video_url}
            controls
            className="mx-auto max-h-[500px]"
          >
            Your browser does not support video playback.
          </video>
        </div>
      )}

      {/* Metadata */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] p-4">
          <h3 className="mb-2 text-sm font-medium">Details</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-[var(--muted-foreground)]">Created</dt>
              <dd>{new Date(video.created_at).toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted-foreground)]">Updated</dt>
              <dd>{new Date(video.updated_at).toLocaleString()}</dd>
            </div>
            {video.published_at && (
              <div className="flex justify-between">
                <dt className="text-[var(--muted-foreground)]">Published</dt>
                <dd>{new Date(video.published_at).toLocaleString()}</dd>
              </div>
            )}
            {video.cost_usd != null && (
              <div className="flex justify-between">
                <dt className="text-[var(--muted-foreground)]">Cost</dt>
                <dd>${video.cost_usd.toFixed(4)}</dd>
              </div>
            )}
          </dl>
        </div>

        <div className="rounded-xl border border-[var(--border)] p-4">
          <h3 className="mb-2 text-sm font-medium">Platforms</h3>
          <dl className="space-y-2 text-sm">
            {video.youtube_id && (
              <div className="flex justify-between">
                <dt className="text-[var(--muted-foreground)]">YouTube</dt>
                <dd>
                  <a
                    href={`https://youtube.com/shorts/${video.youtube_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {video.youtube_id}
                  </a>
                </dd>
              </div>
            )}
            {video.tiktok_id && (
              <div className="flex justify-between">
                <dt className="text-[var(--muted-foreground)]">TikTok</dt>
                <dd>{video.tiktok_id}</dd>
              </div>
            )}
            {video.instagram_id && (
              <div className="flex justify-between">
                <dt className="text-[var(--muted-foreground)]">Instagram</dt>
                <dd>{video.instagram_id}</dd>
              </div>
            )}
            {!video.youtube_id &&
              !video.tiktok_id &&
              !video.instagram_id && (
                <p className="text-[var(--muted-foreground)]">
                  Not published yet
                </p>
              )}
          </dl>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        {video.video_url && (
          <a
            href={video.video_url}
            download
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--accent)]"
          >
            <Download className="h-4 w-4" />
            Download
          </a>
        )}

        {video.status === "ready" && (
          <button className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">
            <Send className="h-4 w-4" />
            Publish
          </button>
        )}

        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </div>
  );
}
