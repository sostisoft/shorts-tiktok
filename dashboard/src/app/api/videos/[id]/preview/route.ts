import { NextRequest, NextResponse } from "next/server";
import { apiGet, APIError } from "@/lib/api-client";
import { getSession } from "@/lib/auth";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getSession();
  if (!session.apiKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  try {
    const result = await apiGet<string>(
      `/api/videos/${id}/preview`,
      session.apiKey,
    );
    if (result.data) {
      return NextResponse.redirect(result.data);
    }
    return NextResponse.json({ error: "Preview not available" }, { status: 404 });
  } catch (err) {
    if (err instanceof APIError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    throw err;
  }
}
