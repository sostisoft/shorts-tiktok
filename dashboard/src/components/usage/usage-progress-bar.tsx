import type { UsageResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export function UsageProgressBar({ usage }: { usage: UsageResponse }) {
  const pct = Math.min(
    (usage.videos_generated / Math.max(usage.plan_limit, 1)) * 100,
    100,
  );
  const color =
    pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-500" : "bg-green-500";

  return (
    <div className="space-y-2 rounded-xl border border-[var(--border)] p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Videos this month</span>
        <span className="text-[var(--muted-foreground)]">
          {usage.videos_generated} / {usage.plan_limit}
        </span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-[var(--muted)]">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
