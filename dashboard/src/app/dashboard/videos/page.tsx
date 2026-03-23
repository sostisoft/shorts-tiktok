"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useVideos } from "@/hooks/use-videos";
import { VideoGrid } from "@/components/videos/video-grid";
import { cn } from "@/lib/utils";

const TABS = [
  { value: undefined, label: "All" },
  { value: "queued,script,images,tts,video,music,compositing", label: "Processing" },
  { value: "ready", label: "Ready" },
  { value: "published", label: "Published" },
  { value: "error", label: "Errors" },
] as const;

export default function VideosPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const { videos, meta, isLoading } = useVideos(page, 12, statusFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Videos</h1>
        <Link
          href="/dashboard/videos/new"
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Create Video
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.label}
            onClick={() => {
              setStatusFilter(tab.value);
              setPage(1);
            }}
            className={cn(
              "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              statusFilter === tab.value
                ? "border-[var(--primary)] text-[var(--foreground)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-52 animate-pulse rounded-xl bg-[var(--muted)]"
            />
          ))}
        </div>
      ) : (
        <VideoGrid videos={videos} />
      )}

      {/* Pagination */}
      {meta && meta.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-[var(--muted-foreground)]">
            Page {page} of {meta.pages}
          </span>
          <button
            disabled={page >= meta.pages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
