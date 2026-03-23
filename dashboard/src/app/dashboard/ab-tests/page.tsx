"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { GitBranch, Plus, Loader2 } from "lucide-react";
import { STYLES } from "@/lib/constants";
import type { APIEnvelope } from "@/lib/types";

interface ABTestItem {
  id: string;
  name: string;
  topic: string;
  template_a: string;
  template_b: string;
  status: string;
  winner: string | null;
  created_at: string;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function ABTestsPage() {
  const { data, isLoading, mutate } = useSWR<APIEnvelope<ABTestItem[]>>("/api/ab-tests", fetcher, { refreshInterval: 10000 });
  const tests = data?.data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [templateA, setTemplateA] = useState("finance");
  const [templateB, setTemplateB] = useState("energetic");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await fetch("/api/ab-tests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, topic, template_a: templateA, template_b: templateB }),
      });
      const d = await res.json();
      if (d.success) { setShowForm(false); setName(""); setTopic(""); mutate(); }
      else setError(d.error || "Failed");
    } catch { setError("Connection failed"); }
    finally { setSaving(false); }
  }

  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="h-5 w-5" />
          <h1 className="text-2xl font-bold">A/B Tests</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]">
          <Plus className="h-4 w-4" /> New Test
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="max-w-lg space-y-4 rounded-xl border border-[var(--border)] p-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Test Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required
              placeholder="e.g., Finance vs Energetic style"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Topic</label>
            <input value={topic} onChange={(e) => setTopic(e.target.value)} required
              placeholder="e.g., 5 tips para ahorrar en supermercado"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Variant A</label>
              <select value={templateA} onChange={(e) => setTemplateA(e.target.value)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Variant B</label>
              <select value={templateB} onChange={(e) => setTemplateB(e.target.value)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? "Creating..." : "Start Test"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm">Cancel</button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="space-y-3">{[1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-[var(--muted)]" />)}</div>
      ) : tests.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-16">
          <GitBranch className="mb-3 h-10 w-10 text-[var(--muted-foreground)] opacity-40" />
          <p className="text-sm text-[var(--muted-foreground)]">No A/B tests yet. Create one to compare video templates.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tests.map((t) => (
            <Link key={t.id} href={`/dashboard/ab-tests/${t.id}`}
              className="block rounded-xl border border-[var(--border)] p-4 transition-shadow hover:shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium">{t.name}</h3>
                  <p className="text-xs text-[var(--muted-foreground)]">{t.topic}</p>
                  <p className="mt-1 text-xs"><span className="capitalize">{t.template_a}</span> vs <span className="capitalize">{t.template_b}</span></p>
                </div>
                <div className="text-right">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[t.status] || statusColors.draft}`}>{t.status}</span>
                  {t.winner && <p className="mt-1 text-xs font-medium text-green-700">Winner: Variant {t.winner.toUpperCase()}</p>}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
