// Judge-response matching. Isomorphic: the map is built client-side from the
// embedded dataset. Matches the normalization in ui/static/script.js.

import type { JudgeInfo, JudgesFile, SummaryRow } from "./types";

export function normalizeRepoKey(repoUrl = ""): string {
  return repoUrl.trim().replace(/\.git$/i, "").toLowerCase();
}

export function buildJudgeMap(judges: JudgesFile): Map<string, JudgeInfo> {
  const map = new Map<string, JudgeInfo>();
  for (const [repoUrl, info] of Object.entries(judges.by_repo ?? {})) {
    map.set(normalizeRepoKey(repoUrl), info);
  }
  return map;
}

export function getJudgeInfoForRow(
  row: SummaryRow | undefined,
  map: Map<string, JudgeInfo>,
): JudgeInfo | null {
  if (!row) return null;
  return map.get(normalizeRepoKey(row.repo)) ?? null;
}
