import { NextRequest, NextResponse } from "next/server";
import { apiPost, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function POST() {
  const session = await getSession();
  if (!session.apiKey) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const result = await apiPost("/api/billing/portal", session.apiKey, {});
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof APIError) return NextResponse.json({ error: err.message }, { status: err.status });
    throw err;
  }
}
