import { NextRequest, NextResponse } from "next/server";
import { apiGet, apiPost, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";
import type { VideoResponse } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.apiKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const params = new URLSearchParams();
  if (searchParams.get("page")) params.set("page", searchParams.get("page")!);
  if (searchParams.get("limit"))
    params.set("limit", searchParams.get("limit")!);
  if (searchParams.get("status"))
    params.set("status", searchParams.get("status")!);

  const path = `/api/videos?${params}`;
  const result = await apiGet<VideoResponse[]>(path, session.apiKey);
  return NextResponse.json(result);
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.apiKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await req.json();
    const result = await apiPost<VideoResponse>(
      "/api/videos",
      session.apiKey,
      body,
    );
    return NextResponse.json(result, { status: 202 });
  } catch (err) {
    if (err instanceof APIError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    throw err;
  }
}
