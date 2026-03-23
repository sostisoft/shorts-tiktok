import Link from "next/link";
import { Film } from "lucide-react";
import type { VideoResponse } from "@/lib/types";
import { VideoStatusBadge } from "./video-status-badge";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function VideoCard({ video }: { video: VideoResponse }) {
  return (
    <Link
      href={`/dashboard/videos/${video.id}`}
      className="group block overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--background)] transition-shadow hover:shadow-md"
    >
      {/* Thumbnail */}
      <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-[var(--muted)] to-[var(--accent)]">
        <Film className="h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
        <div className="absolute right-2 top-2">
          <VideoStatusBadge status={video.status} />
        </div>
      </div>

      {/* Info */}
      <div className="space-y-1.5 p-3">
        <h3 className="line-clamp-2 text-sm font-medium leading-tight group-hover:text-blue-600">
          {video.title || "Untitled Video"}
        </h3>
        <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
          <span>{timeAgo(video.created_at)}</span>
          {video.cost_usd != null && video.cost_usd > 0 && (
            <span>${video.cost_usd.toFixed(2)}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
