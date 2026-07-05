// Pure, isomorphic helpers for rendering the structured AI verdict. The analysis
// is produced by ai/run_ai.py (Claude, structured output) — no regex on prose.

import type { AiAnalysis } from "./types";

export type VerdictTone = "suspicious" | "authentic" | "neutral" | "pending";

export interface VerdictDisplay {
  icon: string;
  tone: VerdictTone;
  label: string;
}

const VERDICT_MAP: Record<string, VerdictDisplay> = {
  authentic: { icon: "✅", tone: "authentic", label: "Authentic" },
  suspicious: { icon: "⚠️", tone: "suspicious", label: "Suspicious" },
  highly_suspicious: { icon: "🚩", tone: "suspicious", label: "Highly suspicious" },
  inconclusive: { icon: "➖", tone: "neutral", label: "Inconclusive" },
};

export function verdictDisplay(ai: AiAnalysis | null): VerdictDisplay {
  if (!ai) return { icon: "⏳", tone: "pending", label: "Pending analysis" };
  return VERDICT_MAP[ai.verdict] ?? { icon: "➖", tone: "neutral", label: ai.verdict };
}

export function isBucketKey(key: string): boolean {
  return /^commits_/.test(key);
}
