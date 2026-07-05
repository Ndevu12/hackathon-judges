import type { AiAnalysis } from "@/lib/types";
import { verdictDisplay } from "@/lib/verdict";
import { cn } from "@/lib/utils";

// AI authenticity verdict icon (from structured analysis) with a title tooltip.
export function VerdictBadge({ ai }: { ai: AiAnalysis | null }) {
  const verdict = verdictDisplay(ai);
  return (
    <span
      title={ai?.summary || verdict.label}
      className={cn(
        "cursor-help text-lg",
        verdict.tone === "pending" && "opacity-50",
        verdict.tone === "neutral" && "opacity-70",
      )}
    >
      {verdict.icon}
    </span>
  );
}
