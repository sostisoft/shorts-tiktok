"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, Clock, Trash2 } from "lucide-react";
import { useChannels } from "@/hooks/use-channels";
import { STYLES } from "@/lib/constants";
import type { APIEnvelope } from "@/lib/types";

interface ScheduleItem {
  id: string;
  cron_expression: string;
  timezone: string;
  topic_pool: string[] | null;
  style: string;
  active: boolean;
  channel_id: string;
  last_run_at: string | null;
  created_at: string;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function SchedulesPage() {
  const { data, isLoading, mutate } = useSWR<APIEnvelope<ScheduleItem[]>>("/api/schedules", fetcher);
  const schedules = data?.data ?? [];
  const { channels } = useChannels();

  const [showForm, setShowForm] = useState(false);
  const [cron, setCron] = useState("0 9 * * 1-5");
  const [tz, setTz] = useState("UTC");
  const [channelId, setChannelId] = useState("");
  const [topics, setTopics] = useState("");
  const [style, setStyle] = useState("finance");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await fetch("/api/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_id: channelId,
          cron_expression: cron,
          timezone: tz,
          topic_pool: topics ? topics.split(",").map((t) => t.trim()).filter(Boolean) : null,
          style,
        }),
      });
      const d = await res.json();
      if (d.success) { setShowForm(false); mutate(); }
      else setError(d.error || "Failed");
    } catch { setError("Connection failed"); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this schedule?")) return;
    await fetch(`/api/schedules/${id}`, { method: "DELETE" });
    mutate();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Schedules</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
        >
          <Plus className="h-4 w-4" /> New Schedule
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] p-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Cron Expression</label>
            <input value={cron} onChange={(e) => setCron(e.target.value)} required
              placeholder="0 9 * * 1-5" className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-sm" />
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">e.g., &quot;0 9 * * 1-5&quot; = weekdays at 9am</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Timezone</label>
            <input value={tz} onChange={(e) => setTz(e.target.value)} required
              placeholder="Europe/Madrid" className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Channel</label>
            <select value={channelId} onChange={(e) => setChannelId(e.target.value)} required
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
              <option value="">Select channel...</option>
              {channels.map((ch) => <option key={ch.id} value={ch.id}>{ch.display_name} ({ch.platform})</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Topics (comma-separated)</label>
            <input value={topics} onChange={(e) => setTopics(e.target.value)}
              placeholder="ahorro, inversión, presupuesto" className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Style</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
              {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50">
              {saving ? "Creating..." : "Create"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm">Cancel</button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="space-y-3">{[1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-[var(--muted)]" />)}</div>
      ) : schedules.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-16">
          <Clock className="mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
          <p className="text-sm text-[var(--muted-foreground)]">No schedules configured</p>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-xl border border-[var(--border)] p-4">
              <div>
                <p className="font-mono text-sm font-medium">{s.cron_expression}</p>
                <p className="text-xs text-[var(--muted-foreground)]">{s.timezone} &middot; {s.style} &middot; {s.active ? "Active" : "Inactive"}</p>
                {s.topic_pool && <p className="mt-1 text-xs text-[var(--muted-foreground)]">Topics: {s.topic_pool.join(", ")}</p>}
              </div>
              <button onClick={() => handleDelete(s.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
