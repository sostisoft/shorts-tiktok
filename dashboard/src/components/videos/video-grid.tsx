import type { VideoResponse } from "@/lib/types";
import { VideoCard } from "./video-card";
import { Video } from "lucide-react";

export function VideoGrid({ videos }: { videos: VideoResponse[] }) {
  if (videos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-16">
        <Video className="mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
        <p className="text-sm text-[var(--muted-foreground)]">
          No videos yet. Create your first one!
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} />
      ))}
    </div>
  );
}
