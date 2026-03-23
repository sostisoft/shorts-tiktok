import { NextRequest, NextResponse } from "next/server";
import { apiPost, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getSession();
  if (!session.apiKey) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { id } = await params;
  try {
    const result = await apiPost(`/api/ab-tests/${id}/evaluate`, session.apiKey, {});
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof APIError) return NextResponse.json({ error: err.message }, { status: err.status });
    throw err;
  }
}
