import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import { getSession } from "@/lib/auth";
import type { UsageResponse } from "@/lib/types";

export async function GET() {
  const session = await getSession();
  if (!session.apiKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const result = await apiGet<UsageResponse>("/api/usage", session.apiKey);
  return NextResponse.json(result);
}
