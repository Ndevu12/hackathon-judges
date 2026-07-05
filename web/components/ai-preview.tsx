import type { AiAnalysis } from "@/lib/types";

// Two-line AI summary preview for the table.
export function AIPreview({ ai }: { ai: AiAnalysis | null }) {
  if (!ai || !ai.summary) {
    return <span className="text-[0.78rem] text-muted-foreground italic">No AI analysis</span>;
  }
  return (
    <span className="line-clamp-2 text-[0.78rem] leading-relaxed text-text-secondary">
      {ai.summary}
    </span>
  );
}
