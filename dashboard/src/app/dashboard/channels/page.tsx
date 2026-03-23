"use client";

import { useState } from "react";
import { Plus, Radio } from "lucide-react";
import { useChannels } from "@/hooks/use-channels";
import { PLATFORMS } from "@/lib/constants";

export default function ChannelsPage() {
  const { channels, isLoading, mutate } = useChannels();
  const [showForm, setShowForm] = useState(false);
  const [platform, setPlatform] = useState("youtube");
  const [displayName, setDisplayName] = useState("");
  const [credentials, setCredentials] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const creds = JSON.parse(credentials);
      const res = await fetch("/api/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform,
          display_name: displayName,
          credentials: creds,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setShowForm(false);
        setDisplayName("");
        setCredentials("");
        mutate();
      } else {
        setError(data.error || "Failed to connect channel");
      }
    } catch {
      setError("Invalid JSON credentials");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Channels</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Connect Channel
        </button>
      </div>

      {/* Connect form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] p-4"
        >
          <div>
            <label className="mb-1 block text-sm font-medium">Platform</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            >
              {PLATFORMS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              Display Name
            </label>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              placeholder="e.g., My YouTube Channel"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              Credentials (JSON)
            </label>
            <textarea
              value={credentials}
              onChange={(e) => setCredentials(e.target.value)}
              required
              rows={4}
              placeholder='{"token": "...", "refresh_token": "..."}'
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-xs"
            />
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              OAuth flow coming soon. Paste credentials JSON for now.
            </p>
          </div>
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
            >
              {saving ? "Connecting..." : "Connect"}
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

      {/* Channel list */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-xl bg-[var(--muted)]"
            />
          ))}
        </div>
      ) : channels.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-16">
          <Radio className="mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
          <p className="text-sm text-[var(--muted-foreground)]">
            No channels connected yet
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map((ch) => (
            <div
              key={ch.id}
              className="flex items-center justify-between rounded-xl border border-[var(--border)] p-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent)]">
                  <Radio className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium">{ch.display_name}</p>
                  <p className="text-xs capitalize text-[var(--muted-foreground)]">
                    {ch.platform}
                  </p>
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ch.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}
              >
                {ch.active ? "Active" : "Inactive"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
