// Pure, isomorphic helpers shared by table cells and the detail drawer so the
// AI verdict is classified identically in both places. Mirrors the regexes in
// the original ui/static/script.js.

export type VerdictTone = "suspicious" | "authentic" | "neutral" | "pending";

export interface Verdict {
  icon: string;
  tone: VerdictTone;
  full: string;
}

const VERDICT_RE = /Overall authenticity assessment:\s*(.+?)$/im;
const SUSPICIOUS_RE = /suspicious|concern|flag|issue|question/i;
const AUTHENTIC_RE = /consistent|authentic|legitimate/i;

export function extractVerdict(aiText: string | null | undefined): Verdict {
  if (!aiText) return { icon: "⏳", tone: "pending", full: "Pending analysis" };
  const match = aiText.match(VERDICT_RE);
  if (!match) return { icon: "⏳", tone: "pending", full: "No assessment found" };
  const verdict = match[1].trim();
  // Suspicious keywords take priority over authentic ones (matches original).
  if (SUSPICIOUS_RE.test(verdict)) return { icon: "⚠️", tone: "suspicious", full: verdict };
  if (AUTHENTIC_RE.test(verdict)) return { icon: "✅", tone: "authentic", full: verdict };
  return { icon: "➖", tone: "neutral", full: verdict };
}

// First two sentences, truncated to 180 chars.
export function getAIPreview(aiText: string | null | undefined): string | null {
  if (!aiText) return null;
  const sentences = aiText.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ");
  return sentences.length > 180 ? sentences.slice(0, 180) + "…" : sentences;
}

// Split AI text into the body and the trailing verdict line so the drawer can
// highlight the verdict without dangerouslySetInnerHTML.
export function splitAtVerdict(aiText: string): { head: string; verdict: string | null } {
  const match = aiText.match(/(Overall authenticity assessment:.*?)$/im);
  if (!match) return { head: aiText, verdict: null };
  const idx = aiText.indexOf(match[1]);
  return { head: aiText.slice(0, idx).trimEnd(), verdict: aiText.slice(idx).trim() };
}

export function isBucketKey(key: string): boolean {
  return /^commits_/.test(key);
}
