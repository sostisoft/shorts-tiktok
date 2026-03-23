"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, Webhook } from "lucide-react";
import { WEBHOOK_EVENTS } from "@/lib/constants";
import type { APIEnvelope, WebhookResponse } from "@/lib/types";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function WebhooksPage() {
  const { data, isLoading, mutate } = useSWR<APIEnvelope<WebhookResponse[]>>(
    "/api/webhooks",
    fetcher,
  );
  const webhooks = data?.data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["video.completed"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function toggleEvent(event: string) {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const res = await fetch("/api/webhooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, events }),
      });
      const data = await res.json();
      if (data.success) {
        setShowForm(false);
        setUrl("");
        setEvents(["video.completed"]);
        mutate();
      } else {
        setError(data.error || "Failed to register webhook");
      }
    } catch {
      setError("Connection failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Webhooks</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Add Webhook
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] p-4"
        >
          <div>
            <label className="mb-1 block text-sm font-medium">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              placeholder="https://example.com/webhook"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Events</label>
            <div className="space-y-2">
              {WEBHOOK_EVENTS.map((event) => (
                <label key={event} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={events.includes(event)}
                    onChange={() => toggleEvent(event)}
                    className="h-4 w-4 rounded border-[var(--border)]"
                  />
                  {event}
                </label>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving || events.length === 0}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
            >
              {saving ? "Registering..." : "Register"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-xl bg-[var(--muted)]"
            />
          ))}
        </div>
      ) : webhooks.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-16">
          <Webhook className="mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
          <p className="text-sm text-[var(--muted-foreground)]">
            No webhooks registered
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
                <th className="px-4 py-2 text-left font-medium">URL</th>
                <th className="px-4 py-2 text-left font-medium">Events</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((wh) => (
                <tr
                  key={wh.id}
                  className="border-b border-[var(--border)] last:border-0"
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    {wh.url.length > 50 ? wh.url.slice(0, 50) + "..." : wh.url}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {wh.events.map((ev) => (
                        <span
                          key={ev}
                          className="rounded bg-[var(--accent)] px-1.5 py-0.5 text-xs"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${wh.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}
                    >
                      {wh.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
