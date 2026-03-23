import type { APIEnvelope } from "./types";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function apiFetch<T>(
  path: string,
  apiKey: string,
  options: RequestInit = {},
): Promise<APIEnvelope<T>> {
  const url = `${API_BASE_URL}${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...options.headers,
    },
    cache: "no-store",
  });

  if (res.status === 401) {
    throw new APIError(401, "Invalid API key");
  }

  if (res.status === 403) {
    throw new APIError(403, "Forbidden");
  }

  if (res.status === 404) {
    throw new APIError(404, "Not found");
  }

  if (res.status === 429) {
    throw new APIError(429, "Rate limit exceeded");
  }

  // Handle redirects (e.g., preview)
  if (res.status === 307 || res.status === 302) {
    const location = res.headers.get("location");
    return { success: true, data: location as T, error: null, meta: null };
  }

  const body = await res.json();

  if (!res.ok) {
    throw new APIError(res.status, body.detail || body.error || "Unknown error");
  }

  return body as APIEnvelope<T>;
}

export async function apiGet<T>(path: string, apiKey: string) {
  return apiFetch<T>(path, apiKey);
}

export async function apiPost<T>(
  path: string,
  apiKey: string,
  data: unknown,
) {
  return apiFetch<T>(path, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function apiDelete<T>(path: string, apiKey: string) {
  return apiFetch<T>(path, apiKey, { method: "DELETE" });
}
