// TypeScript types mirroring backend Pydantic schemas

export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface APIEnvelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  meta: PaginationMeta | null;
}

// --- Video ---

export const VIDEO_STATUSES = [
  "queued",
  "script",
  "images",
  "tts",
  "video",
  "music",
  "compositing",
  "ready",
  "publishing",
  "published",
  "error",
  "cancelled",
] as const;

export type VideoStatus = (typeof VIDEO_STATUSES)[number];

export interface VideoResponse {
  id: string;
  job_id: string;
  title: string | null;
  description: string | null;
  status: VideoStatus;
  video_url: string | null;
  preview_url: string | null;
  cost_usd: number | null;
  youtube_id: string | null;
  tiktok_id: string | null;
  instagram_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface VideoCreate {
  topic?: string | null;
  style?: string;
  channel_id?: string | null;
  auto_publish?: boolean;
}

export interface VideoPublish {
  channel_id: string;
}

// --- Channel ---

export interface ChannelResponse {
  id: string;
  platform: string;
  display_name: string;
  active: boolean;
  created_at: string;
}

export interface ChannelCreate {
  platform: string;
  display_name: string;
  credentials: Record<string, unknown>;
}

// --- Usage ---

export interface UsageResponse {
  month: string;
  videos_generated: number;
  videos_published: number;
  api_cost_usd: number;
  plan_limit: number;
}

// --- Webhook ---

export interface WebhookResponse {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
}

export interface WebhookCreate {
  url: string;
  events: string[];
}

// --- Plan ---

export type PlanTier = "starter" | "growth" | "agency";

// --- Session ---

export interface SessionData {
  apiKey: string;
  tenantName: string;
  plan: PlanTier;
  isAdmin: boolean;
}
