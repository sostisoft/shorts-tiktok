"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Film, Loader2, Copy, Check } from "lucide-react";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();

      if (data.success) {
        setApiKey(data.apiKey);
      } else {
        setError(data.error || "Registration failed");
      }
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  function copyKey() {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (apiKey) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-green-100">
            <Check className="h-7 w-7 text-green-700" />
          </div>
          <h1 className="text-2xl font-bold">Account Created!</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Save your API key — it cannot be recovered.
          </p>
          <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-3">
            <code className="flex-1 break-all text-xs">{apiKey}</code>
            <button onClick={copyKey} className="shrink-0 rounded p-1.5 hover:bg-[var(--accent)]">
              {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
          <p className="text-xs text-yellow-600">
            Free trial: 3 videos. Upgrade anytime from the dashboard.
          </p>
          <button
            onClick={() => router.push("/dashboard")}
            className="w-full rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)]">
            <Film className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-2xl font-bold">Create Account</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Start with 3 free videos
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <input
              value={name} onChange={(e) => setName(e.target.value)} required
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
            />
          </div>
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
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              required minLength={8}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</div>
          )}

          <button
            type="submit" disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Creating..." : "Create Account"}
          </button>
        </form>

        <p className="text-center text-sm text-[var(--muted-foreground)]">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-600 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
