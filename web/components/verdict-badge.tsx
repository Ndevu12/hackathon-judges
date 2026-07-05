import { extractVerdict } from "@/lib/verdict";
import { cn } from "@/lib/utils";

// AI authenticity verdict icon with a native title tooltip (parity with the
// original ⚠️/✅/➖/⏳ mapping).
export function VerdictBadge({ aiText }: { aiText: string | null }) {
  const verdict = extractVerdict(aiText);
  return (
    <span
      title={verdict.full}
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
