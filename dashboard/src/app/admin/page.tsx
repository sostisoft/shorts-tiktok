"use client";

import useSWR from "swr";
import { Shield, Users, Activity, DollarSign, Layers } from "lucide-react";
import type { APIEnvelope } from "@/lib/types";

interface AdminMetrics {
  total_tenants: number;
  active_tenants: number;
  total_videos_this_month: number;
  total_published_this_month: number;
  total_cost_this_month: number;
  videos_by_status: Record<string, number>;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function AdminOverview() {
  const { data, isLoading } = useSWR<APIEnvelope<AdminMetrics>>("/api/admin/metrics", fetcher, { refreshInterval: 30000 });
  const metrics = data?.data;

  const cards = [
    { label: "Total Tenants", value: metrics?.total_tenants ?? "--", icon: Users, bg: "bg-blue-100", fg: "text-blue-700" },
    { label: "Active Tenants", value: metrics?.active_tenants ?? "--", icon: Users, bg: "bg-green-100", fg: "text-green-700" },
    { label: "Videos (month)", value: metrics?.total_videos_this_month ?? "--", icon: Activity, bg: "bg-purple-100", fg: "text-purple-700" },
    { label: "Published (month)", value: metrics?.total_published_this_month ?? "--", icon: Layers, bg: "bg-yellow-100", fg: "text-yellow-700" },
    { label: "API Cost (month)", value: metrics ? `$${metrics.total_cost_this_month.toFixed(2)}` : "--", icon: DollarSign, bg: "bg-red-100", fg: "text-red-700" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Shield className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Admin Panel</h1>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((c) => (
          <div key={c.label} className="rounded-xl border border-[var(--border)] p-4">
            <div className="flex items-center gap-2">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${c.bg}`}>
                <c.icon className={`h-4 w-4 ${c.fg}`} />
              </div>
              <span className="text-xs text-[var(--muted-foreground)]">{c.label}</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{isLoading ? "..." : c.value}</p>
          </div>
        ))}
      </div>

      {metrics?.videos_by_status && Object.keys(metrics.videos_by_status).length > 0 && (
        <div className="rounded-xl border border-[var(--border)] p-4">
          <h2 className="mb-3 text-sm font-medium">Videos by Status</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(metrics.videos_by_status).map(([status, count]) => (
              <span key={status} className="rounded-full bg-[var(--muted)] px-3 py-1 text-xs">
                {status}: <strong>{count}</strong>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
