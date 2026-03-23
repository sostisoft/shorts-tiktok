"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Film,
  LayoutDashboard,
  Video,
  Radio,
  BarChart3,
  Webhook,
  Shield,
  Clock,
  CreditCard,
  TrendingUp,
  Flame,
  GitBranch,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/videos", label: "Videos", icon: Video },
  { href: "/dashboard/channels", label: "Channels", icon: Radio },
  { href: "/dashboard/schedules", label: "Schedules", icon: Clock },
  { href: "/dashboard/analytics", label: "Analytics", icon: TrendingUp },
  { href: "/dashboard/trends", label: "Trends", icon: Flame },
  { href: "/dashboard/ab-tests", label: "A/B Tests", icon: GitBranch },
  { href: "/dashboard/usage", label: "Usage", icon: BarChart3 },
  { href: "/dashboard/billing", label: "Billing", icon: CreditCard },
  { href: "/dashboard/webhooks", label: "Webhooks", icon: Webhook },
];

export function Sidebar({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-[var(--border)] bg-[var(--background)] md:block">
      <div className="flex h-14 items-center gap-2 border-b border-[var(--border)] px-4">
        <Film className="h-6 w-6" />
        <span className="text-lg font-bold">ShortForge</span>
      </div>

      <nav className="space-y-1 p-3">
        {navItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)]",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}

        {isAdmin && (
          <>
            <div className="my-3 border-t border-[var(--border)]" />
            <Link
              href="/admin"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                pathname.startsWith("/admin")
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)]",
              )}
            >
              <Shield className="h-4 w-4" />
              Admin
            </Link>
          </>
        )}
      </nav>
    </aside>
  );
}
