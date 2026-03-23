import { NextRequest, NextResponse } from "next/server";
import { setSession } from "@/lib/auth";
import type { PlanTier } from "@/lib/types";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { name, email, password } = await req.json();

  const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });

  const data = await res.json();

  if (!data.success || !data.data) {
    return NextResponse.json(
      { success: false, error: data.detail || data.error || "Registration failed" },
      { status: res.status },
    );
  }

  const tenant = data.data;

  await setSession({
    apiKey: tenant.api_key,
    tenantName: tenant.name,
    plan: tenant.plan as PlanTier,
    isAdmin: tenant.is_admin,
  });

  return NextResponse.json({
    success: true,
    apiKey: tenant.api_key,
    tenantName: tenant.name,
    plan: tenant.plan,
  });
}
