import { NextRequest, NextResponse } from "next/server";
import { apiPost, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getSession();
  if (!session.apiKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  try {
    const body = await req.json();
    const result = await apiPost(
      `/api/videos/${id}/publish`,
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
