import type { VideoStatus } from "@/lib/types";
import { PIPELINE_PHASES } from "@/lib/constants";
import { Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_TO_PHASE_INDEX: Record<string, number> = {
  queued: -1,
  script: 0,
  images: 1,
  tts: 2,
  video: 3,
  music: 4,
  compositing: 5,
  ready: 6,
  publishing: 6,
  published: 6,
  error: -2,
  cancelled: -2,
};

export function PipelineProgress({ status }: { status: VideoStatus }) {
  const currentIdx = STATUS_TO_PHASE_INDEX[status] ?? -1;
  const isError = status === "error";
  const isDone = currentIdx >= 6;

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_PHASES.map((phase, idx) => {
        const isActive = idx === currentIdx;
        const isComplete = idx < currentIdx || isDone;
        const isFailed = isError && idx === currentIdx;

        return (
          <div key={phase.status} className="flex items-center gap-1">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs transition-all",
                  isComplete && "border-green-500 bg-green-500 text-white",
                  isActive &&
                    !isFailed &&
                    "border-blue-500 bg-blue-50 text-blue-600",
                  isFailed && "border-red-500 bg-red-50 text-red-600",
                  !isComplete &&
                    !isActive &&
                    "border-[var(--border)] text-[var(--muted-foreground)]",
                )}
              >
                {isComplete ? (
                  <Check className="h-4 w-4" />
                ) : isFailed ? (
                  <X className="h-4 w-4" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  idx + 1
                )}
              </div>
              <span className="max-w-16 text-center text-[10px] leading-tight text-[var(--muted-foreground)]">
                {phase.name}
              </span>
            </div>
            {idx < PIPELINE_PHASES.length - 1 && (
              <div
                className={cn(
                  "mb-4 h-0.5 w-4 sm:w-6",
                  idx < currentIdx || isDone
                    ? "bg-green-500"
                    : "bg-[var(--border)]",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
