import type { JudgeInfo } from "@/lib/types";

function tooltipText(info: JudgeInfo): string {
  if (!info.responses?.length) return "No judge responses";
  return info.responses
    .map((r, i) => `#${i + 1}: ${r.score}${r.thoughts ? ` — ${r.thoughts}` : ""}`)
    .join("\n");
}

// Average judge score chip with a native title tooltip of individual responses.
export function JudgeCell({ info }: { info: JudgeInfo | null }) {
  if (!info || !info.responses?.length) {
    return <span className="text-muted-foreground">—</span>;
  }
  const avg = Number(info.average_score || 0).toFixed(1);
  return (
    <span
      title={tooltipText(info)}
      className="inline-flex items-baseline gap-0.5 rounded-md border border-ok/25 bg-ok/10 px-2 py-1 font-mono text-[0.8rem] font-semibold text-ok"
    >
      {avg}
      <span className="text-[0.65rem] font-normal text-muted-foreground">/{info.responses.length}</span>
    </span>
  );
}
