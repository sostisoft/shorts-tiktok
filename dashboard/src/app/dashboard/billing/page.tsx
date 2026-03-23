"use client";

import { useState } from "react";
import useSWR from "swr";
import { CreditCard, Check, Loader2 } from "lucide-react";
import type { APIEnvelope } from "@/lib/types";
import { cn } from "@/lib/utils";

interface BillingStatus {
  plan: string;
  subscription_status: string | null;
  stripe_customer_id: string | null;
  current_period_end: string | null;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const PLANS = [
  { id: "starter", name: "Starter", price: "$99/mo", limit: "15 videos/mo", features: ["Stock images", "Ken Burns video", "Edge TTS", "1 channel"] },
  { id: "growth", name: "Growth", price: "$249/mo", limit: "30 videos/mo", features: ["AI images (FLUX)", "Ken Burns video", "Edge TTS", "3 channels"] },
  { id: "agency", name: "Agency", price: "$499/mo", limit: "90 videos/mo", features: ["AI images (FLUX)", "AI video (Kling)", "ElevenLabs TTS", "10 channels"] },
];

export default function BillingPage() {
  const { data } = useSWR<APIEnvelope<BillingStatus>>("/api/billing/status", fetcher);
  const status = data?.data;
  const [loading, setLoading] = useState("");

  async function handleCheckout(plan: string) {
    setLoading(plan);
    try {
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const d = await res.json();
      if (d.data?.url) window.location.href = d.data.url;
    } finally {
      setLoading("");
    }
  }

  async function handlePortal() {
    setLoading("portal");
    try {
      const res = await fetch("/api/billing/portal", { method: "POST" });
      const d = await res.json();
      if (d.data?.url) window.location.href = d.data.url;
    } finally {
      setLoading("");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Billing</h1>

      {status && (
        <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] p-4">
          <CreditCard className="h-5 w-5 text-[var(--muted-foreground)]" />
          <div className="flex-1">
            <p className="text-sm font-medium">Current Plan: <span className="capitalize">{status.plan}</span></p>
            {status.subscription_status && (
              <p className="text-xs text-[var(--muted-foreground)]">Status: {status.subscription_status}</p>
            )}
            {status.current_period_end && (
              <p className="text-xs text-[var(--muted-foreground)]">Renews: {new Date(status.current_period_end).toLocaleDateString()}</p>
            )}
          </div>
          {status.stripe_customer_id && (
            <button
              onClick={handlePortal}
              disabled={loading === "portal"}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--accent)]"
            >
              {loading === "portal" ? "Loading..." : "Manage Billing"}
            </button>
          )}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-3">
        {PLANS.map((plan) => {
          const isCurrent = status?.plan === plan.id;
          return (
            <div key={plan.id} className={cn("rounded-xl border-2 p-6", isCurrent ? "border-blue-500" : "border-[var(--border)]")}>
              {isCurrent && <span className="mb-2 inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">Current</span>}
              <h3 className="text-lg font-bold">{plan.name}</h3>
              <p className="mt-1 text-2xl font-bold">{plan.price}</p>
              <p className="text-xs text-[var(--muted-foreground)]">{plan.limit}</p>
              <ul className="mt-4 space-y-2">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-green-600" /> {f}
                  </li>
                ))}
              </ul>
              {!isCurrent && (
                <button
                  onClick={() => handleCheckout(plan.id)}
                  disabled={!!loading}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
                >
                  {loading === plan.id && <Loader2 className="h-4 w-4 animate-spin" />}
                  {loading === plan.id ? "Redirecting..." : "Upgrade"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
