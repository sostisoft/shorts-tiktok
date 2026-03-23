"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { STYLES } from "@/lib/constants";
import type { ChannelResponse } from "@/lib/types";

export function CreateVideoForm({
  channels,
}: {
  channels: ChannelResponse[];
}) {
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("finance");
  const [channelId, setChannelId] = useState("");
  const [autoPublish, setAutoPublish] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic || null,
          style,
          channel_id: channelId || null,
          auto_publish: autoPublish,
        }),
      });

      const data = await res.json();
      if (data.success && data.data) {
        router.push(`/dashboard/videos/${data.data.id}`);
      } else {
        setError(data.error || "Failed to create video");
      }
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-5">
      <div>
        <label htmlFor="topic" className="mb-1 block text-sm font-medium">
          Topic (optional)
        </label>
        <input
          id="topic"
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g., 5 tips para ahorrar en supermercado"
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
        />
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Leave empty for auto-generated topic
        </p>
      </div>

      <div>
        <label htmlFor="style" className="mb-1 block text-sm font-medium">
          Style
        </label>
        <select
          id="style"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          {STYLES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {channels.length > 0 && (
        <>
          <div>
            <label
              htmlFor="channel"
              className="mb-1 block text-sm font-medium"
            >
              Channel (optional)
            </label>
            <select
              id="channel"
              value={channelId}
              onChange={(e) => {
                setChannelId(e.target.value);
                if (!e.target.value) setAutoPublish(false);
              }}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="">No channel</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.display_name} ({ch.platform})
                </option>
              ))}
            </select>
          </div>

          {channelId && (
            <div className="flex items-center gap-2">
              <input
                id="autoPublish"
                type="checkbox"
                checked={autoPublish}
                onChange={(e) => setAutoPublish(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--border)]"
              />
              <label htmlFor="autoPublish" className="text-sm">
                Auto-publish when ready
              </label>
            </div>
          )}
        </>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {loading ? "Creating..." : "Create Video"}
      </button>
    </form>
  );
}
