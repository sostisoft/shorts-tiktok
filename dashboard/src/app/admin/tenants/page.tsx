"use client";

import { useState } from "react";
import useSWR from "swr";
import { Users } from "lucide-react";
import type { APIEnvelope } from "@/lib/types";

interface TenantItem {
  id: string;
  name: string;
  email: string;
  plan: string;
  active: boolean;
  is_admin: boolean;
  videos_generated: number;
  created_at: string;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function TenantsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useSWR<APIEnvelope<TenantItem[]>>(
    `/api/admin/tenants?page=${page}&limit=20`,
    fetcher,
    { refreshInterval: 15000 },
  );
  const tenants = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Users className="h-5 w-5" />
        <h1 className="text-2xl font-bold">Tenants</h1>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-[var(--muted)]" />)}</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Email</th>
                <th className="px-4 py-2 text-left font-medium">Plan</th>
                <th className="px-4 py-2 text-left font-medium">Videos</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-4 py-3 font-medium">{t.name} {t.is_admin && <span className="ml-1 text-xs text-purple-600">(admin)</span>}</td>
                  <td className="px-4 py-3 text-[var(--muted-foreground)]">{t.email}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs capitalize">{t.plan}</span></td>
                  <td className="px-4 py-3">{t.videos_generated}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${t.active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {t.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {meta && meta.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50">Previous</button>
          <span className="text-sm text-[var(--muted-foreground)]">Page {page} of {meta.pages}</span>
          <button disabled={page >= meta.pages} onClick={() => setPage((p) => p + 1)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50">Next</button>
        </div>
      )}
    </div>
  );
}
