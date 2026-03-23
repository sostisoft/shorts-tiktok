import { NextRequest, NextResponse } from "next/server";
import { apiGet, apiPost, APIError } from "@/lib/api-client";
import { setSession } from "@/lib/auth";
import type { PlanTier } from "@/lib/types";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

interface MeData {
  id: string;
  name: string;
  email: string;
  plan: PlanTier;
  is_admin: boolean;
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  // Support two login modes: API key or email/password
  let apiKey: string;

  if (body.apiKey) {
    // API key login — validate by calling /api/me
    apiKey = body.apiKey;
  } else if (body.email && body.password) {
    // Email/password login
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: body.email, password: body.password }),
      });
      const data = await res.json();
      if (!data.success || !data.data?.api_key) {
        return NextResponse.json(
          { success: false, error: data.detail || "Invalid credentials" },
          { status: 401 },
        );
      }
      apiKey = data.data.api_key;
    } catch {
      return NextResponse.json(
        { success: false, error: "Authentication failed" },
        { status: 401 },
      );
    }
  } else {
    return NextResponse.json(
      { success: false, error: "Provide apiKey or email+password" },
      { status: 400 },
    );
  }

  try {
    // Get real tenant info from /api/me
    const meResult = await apiGet<MeData>("/api/me", apiKey);

    if (!meResult.success || !meResult.data) {
      return NextResponse.json(
        { success: false, error: "Invalid API key" },
        { status: 401 },
      );
    }

    const me = meResult.data;

    await setSession({
      apiKey,
      tenantName: me.name,
      plan: me.plan,
      isAdmin: me.is_admin,
    });

    return NextResponse.json({
      success: true,
      tenantName: me.name,
      plan: me.plan,
      isAdmin: me.is_admin,
    });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Authentication failed";
    return NextResponse.json(
      { success: false, error: message },
      { status: 401 },
    );
  }
}
