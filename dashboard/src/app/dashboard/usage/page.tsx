"use client";

import { useUsage } from "@/hooks/use-usage";
import { UsageProgressBar } from "@/components/usage/usage-progress-bar";
import { BarChart3, Video, DollarSign, Calendar } from "lucide-react";

export default function UsagePage() {
  const { usage, isLoading } = useUsage();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Usage</h1>
        <div className="h-20 animate-pulse rounded-xl bg-[var(--muted)]" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl bg-[var(--muted)]"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!usage) {
    return (
      <div className="py-16 text-center text-[var(--muted-foreground)]">
        Unable to load usage data
      </div>
    );
  }

  const stats = [
    {
      label: "Month",
      value: usage.month,
      icon: Calendar,
      bg: "bg-gray-100",
      fg: "text-gray-700",
    },
    {
      label: "Generated",
      value: usage.videos_generated,
      icon: Video,
      bg: "bg-blue-100",
      fg: "text-blue-700",
    },
    {
      label: "Published",
      value: usage.videos_published,
      icon: Video,
      bg: "bg-green-100",
      fg: "text-green-700",
    },
    {
      label: "API Cost",
      value: `$${usage.api_cost_usd.toFixed(2)}`,
      icon: DollarSign,
      bg: "bg-yellow-100",
      fg: "text-yellow-700",
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Usage</h1>

      <UsageProgressBar usage={usage} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="flex items-center gap-3 rounded-xl border border-[var(--border)] p-4"
          >
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.bg}`}
            >
              <s.icon className={`h-5 w-5 ${s.fg}`} />
            </div>
            <div>
              <p className="text-xl font-bold">{s.value}</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                {s.label}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[var(--border)] p-4">
        <h2 className="mb-2 text-sm font-medium">Plan Limit</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Your plan allows up to {usage.plan_limit} videos per month. You have
          used {usage.videos_generated} so far.{" "}
          {usage.plan_limit - usage.videos_generated > 0
            ? `${usage.plan_limit - usage.videos_generated} remaining.`
            : "Limit reached."}
        </p>
      </div>
    </div>
  );
}
