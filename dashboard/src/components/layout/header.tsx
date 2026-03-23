"use client";

import { useRouter } from "next/navigation";
import { LogOut, Menu } from "lucide-react";
import type { PlanTier } from "@/lib/types";

export function Header({
  tenantName,
  plan,
  onMenuClick,
}: {
  tenantName: string;
  plan: PlanTier;
  onMenuClick?: () => void;
}) {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  const planColors: Record<PlanTier, string> = {
    starter: "bg-gray-100 text-gray-700",
    growth: "bg-blue-100 text-blue-700",
    agency: "bg-purple-100 text-purple-700",
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] px-4">
      <div className="flex items-center gap-3">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="rounded-lg p-1.5 hover:bg-[var(--accent)] md:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <span className="text-sm font-medium">{tenantName}</span>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${planColors[plan]}`}
        >
          {plan}
        </span>
      </div>

      <button
        onClick={handleLogout}
        className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
      >
        <LogOut className="h-4 w-4" />
        Sign Out
      </button>
    </header>
  );
}
