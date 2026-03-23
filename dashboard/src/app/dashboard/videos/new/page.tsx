"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useChannels } from "@/hooks/use-channels";
import { CreateVideoForm } from "@/components/videos/create-video-form";

export default function NewVideoPage() {
  const router = useRouter();
  const { channels } = useChannels();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="rounded-lg p-1.5 hover:bg-[var(--accent)]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold">Create Video</h1>
      </div>

      <CreateVideoForm channels={channels} />
    </div>
  );
}
