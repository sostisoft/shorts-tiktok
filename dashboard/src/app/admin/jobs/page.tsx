"use client";

import { useState } from "react";
import useSWR from "swr";
import { Activity } from "lucide-react";
import { VideoStatusBadge } from "@/components/videos/video-status-badge";
import type { APIEnvelope, VideoStatus } from "@/lib/types";

interface AdminJob {
  id: string;
  job_id: string;
  tenant_id: string;
  tenant_name: string;
  title: string | null;
  status: VideoStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function JobsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const params = new URLSearchParams({ page: String(page), limit: "20" });
  if (statusFilter) params.set("status", statusFilter);

  const { data, isLoading } = useSWR<APIEnvelope<AdminJob[]>>(
    `/api/admin/jobs?${params}`,
    fetcher,
    { refreshInterval: 5000 },
  );
  const jobs = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          <h1 className="text-2xl font-bold">Job Queue</h1>
        </div>
        <select
          value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm"
        >
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="error">Error</option>
          <option value="ready">Ready</option>
          <option value="published">Published</option>
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[1, 2, 3, 4].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-[var(--muted)]" />)}</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
                <th className="px-4 py-2 text-left font-medium">Job</th>
                <th className="px-4 py-2 text-left font-medium">Tenant</th>
                <th className="px-4 py-2 text-left font-medium">Title</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-left font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{j.job_id}</td>
                  <td className="px-4 py-3">{j.tenant_name}</td>
                  <td className="px-4 py-3">{j.title || "\u2014"}</td>
                  <td className="px-4 py-3"><VideoStatusBadge status={j.status} /></td>
                  <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">{new Date(j.updated_at).toLocaleString()}</td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">No jobs found</td></tr>
              )}
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
