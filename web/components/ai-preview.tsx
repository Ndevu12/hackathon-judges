import { getAIPreview } from "@/lib/verdict";

// Two-sentence AI summary preview, clamped to two lines.
export function AIPreview({ aiText }: { aiText: string | null }) {
  const preview = getAIPreview(aiText);
  if (!preview) {
    return <span className="text-[0.78rem] text-muted-foreground italic">No AI analysis</span>;
  }
  return (
    <span className="line-clamp-2 text-[0.78rem] leading-relaxed text-text-secondary">
      {preview}
    </span>
  );
}
