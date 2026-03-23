import { NextRequest, NextResponse } from "next/server";
import { apiGet, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getSession();
  if (!session.apiKey) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { id } = await params;
  try {
    const result = await apiGet(`/api/ab-tests/${id}`, session.apiKey);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof APIError) return NextResponse.json({ error: err.message }, { status: err.status });
    throw err;
  }
}
