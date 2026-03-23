import type { VideoStatus } from "./types";

export const PIPELINE_PHASES = [
  { name: "Script", status: "script" as VideoStatus },
  { name: "Images", status: "images" as VideoStatus },
  { name: "TTS", status: "tts" as VideoStatus },
  { name: "Video", status: "video" as VideoStatus },
  { name: "Music", status: "music" as VideoStatus },
  { name: "Compositing", status: "compositing" as VideoStatus },
] as const;

export const STATUS_CONFIG: Record<
  VideoStatus,
  { label: string; color: string; bgColor: string }
> = {
  queued: { label: "Queued", color: "text-gray-600", bgColor: "bg-gray-100" },
  script: { label: "Script", color: "text-blue-600", bgColor: "bg-blue-100" },
  images: { label: "Images", color: "text-blue-600", bgColor: "bg-blue-100" },
  tts: { label: "TTS", color: "text-blue-600", bgColor: "bg-blue-100" },
  video: { label: "Video", color: "text-blue-600", bgColor: "bg-blue-100" },
  music: { label: "Music", color: "text-blue-600", bgColor: "bg-blue-100" },
  compositing: {
    label: "Compositing",
    color: "text-blue-600",
    bgColor: "bg-blue-100",
  },
  ready: { label: "Ready", color: "text-yellow-700", bgColor: "bg-yellow-100" },
  publishing: {
    label: "Publishing",
    color: "text-purple-600",
    bgColor: "bg-purple-100",
  },
  published: {
    label: "Published",
    color: "text-green-700",
    bgColor: "bg-green-100",
  },
  error: { label: "Error", color: "text-red-700", bgColor: "bg-red-100" },
  cancelled: {
    label: "Cancelled",
    color: "text-gray-500",
    bgColor: "bg-gray-100",
  },
};

export const PROCESSING_STATUSES: VideoStatus[] = [
  "queued",
  "script",
  "images",
  "tts",
  "video",
  "music",
  "compositing",
  "publishing",
];

export const PLATFORMS = [
  { value: "youtube", label: "YouTube" },
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
] as const;

export const STYLES = [
  { value: "finance", label: "Finance" },
  { value: "educational", label: "Educational" },
  { value: "documentary", label: "Documentary" },
  { value: "energetic", label: "Energetic" },
  { value: "listicle", label: "Listicle" },
  { value: "storytelling", label: "Storytelling" },
] as const;

export const WEBHOOK_EVENTS = [
  "video.completed",
  "video.error",
  "video.published",
] as const;
