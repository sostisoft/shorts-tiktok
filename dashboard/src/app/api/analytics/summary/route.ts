import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function GET() {
  const session = await getSession();
  if (!session.apiKey) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const result = await apiGet("/api/analytics/summary", session.apiKey);
  return NextResponse.json(result);
}
