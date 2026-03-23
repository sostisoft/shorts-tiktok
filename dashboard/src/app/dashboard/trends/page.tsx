"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Flame, Loader2, Sparkles, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface Suggestion {
  topic: string;
  reasoning: string;
  estimated_interest: string;
}

const interestColors: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-gray-100 text-gray-600",
};

export default function TrendsPage() {
  const [niche, setNiche] = useState("finanzas personales");
  const [count, setCount] = useState(10);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuggestions([]);

    try {
      const res = await fetch("/api/trends/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ niche, count }),
      });
      const data = await res.json();
      if (data.success && data.data) {
        setSuggestions(data.data);
      } else {
        setError(data.error || "Failed to generate suggestions");
      }
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  function useTopic(topic: string) {
    router.push(`/dashboard/videos/new?topic=${encodeURIComponent(topic)}`);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Flame className="h-6 w-6 text-orange-500" />
        <h1 className="text-2xl font-bold">Trend Explorer</h1>
      </div>

      <form onSubmit={handleGenerate} className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium">Niche</label>
          <input
            value={niche} onChange={(e) => setNiche(e.target.value)} required
            placeholder="e.g., finanzas personales, fitness, cocina..."
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
          />
        </div>
        <div className="w-24">
          <label className="mb-1 block text-sm font-medium">Count</label>
          <input
            type="number" value={count} onChange={(e) => setCount(Number(e.target.value))}
            min={1} max={20}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit" disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {loading ? "Generating..." : "Generate Ideas"}
        </button>
      </form>

      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {suggestions.length > 0 && (
        <div className="space-y-3">
          {suggestions.map((s, i) => (
            <div key={i} className="flex items-start justify-between gap-4 rounded-xl border border-[var(--border)] p-4">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium">{s.topic}</h3>
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium capitalize", interestColors[s.estimated_interest] || interestColors.medium)}>
                    {s.estimated_interest}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">{s.reasoning}</p>
              </div>
              <button
                onClick={() => useTopic(s.topic)}
                className="flex shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--accent)]"
              >
                Use <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {!loading && suggestions.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] py-16 text-center">
          <Flame className="mx-auto mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
          <p className="text-sm text-[var(--muted-foreground)]">
            Enter a niche and generate AI-powered topic suggestions
          </p>
        </div>
      )}
    </div>
  );
}
