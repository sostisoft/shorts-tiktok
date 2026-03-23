import { NextRequest, NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.apiKey) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { searchParams } = new URL(req.url);
  const params = new URLSearchParams();
  if (searchParams.get("page")) params.set("page", searchParams.get("page")!);
  if (searchParams.get("limit")) params.set("limit", searchParams.get("limit")!);
  const result = await apiGet(`/api/admin/tenants?${params}`, session.apiKey);
  return NextResponse.json(result);
}
