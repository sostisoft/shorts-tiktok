"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Film, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "apikey" | "email";

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("email");
  const [apiKey, setApiKey] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const body = tab === "apikey" ? { apiKey } : { email, password };

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (data.success) {
        router.push(data.isAdmin ? "/admin" : "/dashboard");
      } else {
        setError(data.error || "Invalid credentials");
      }
    } catch {
      setError("Connection failed. Is the API running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)]">
            <Film className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-2xl font-bold">ShortForge</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Sign in to your dashboard
          </p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--border)]">
          {(["email", "apikey"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "flex-1 border-b-2 py-2 text-sm font-medium",
                tab === t
                  ? "border-[var(--primary)] text-[var(--foreground)]"
                  : "border-transparent text-[var(--muted-foreground)]",
              )}
            >
              {t === "email" ? "Email" : "API Key"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === "email" ? (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium">Email</label>
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Password</label>
                <input
                  type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
              </div>
            </>
          ) : (
            <div>
              <label className="mb-1 block text-sm font-medium">API Key</label>
              <input
                type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                required placeholder="sf_..."
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</div>
          )}

          <button
            type="submit" disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="text-center text-sm text-[var(--muted-foreground)]">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-blue-600 hover:underline">Create one</Link>
        </p>
      </div>
    </div>
  );
}
