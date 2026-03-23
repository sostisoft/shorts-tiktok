import type { VideoStatus } from "@/lib/types";
import { STATUS_CONFIG } from "@/lib/constants";

export function VideoStatusBadge({ status }: { status: VideoStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.queued;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bgColor} ${config.color}`}
    >
      {config.label}
    </span>
  );
}
