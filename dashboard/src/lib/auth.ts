import { getIronSession, type SessionOptions } from "iron-session";
import { cookies } from "next/headers";
import type { SessionData } from "./types";
import crypto from "crypto";

const SESSION_OPTIONS: SessionOptions = {
  password: process.env.SESSION_SECRET || "change-me-to-a-random-32-character-string!!",
  cookieName: "sf_session",
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    maxAge: 60 * 60 * 24 * 7, // 7 days
  },
};

export async function getSession() {
  const cookieStore = await cookies();
  return getIronSession<SessionData>(cookieStore, SESSION_OPTIONS);
}

export async function setSession(data: SessionData) {
  const session = await getSession();
  session.apiKey = data.apiKey;
  session.tenantName = data.tenantName;
  session.plan = data.plan;
  session.isAdmin = data.isAdmin;
  await session.save();
}

export async function clearSession() {
  const session = await getSession();
  session.destroy();
}

export function isAdminKey(apiKey: string): boolean {
  const adminHash = process.env.ADMIN_API_KEY_HASH;
  if (!adminHash) return false;
  const keyHash = crypto.createHash("sha256").update(apiKey).digest("hex");
  return keyHash === adminHash;
}
