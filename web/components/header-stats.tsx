import type { SummaryRow } from "@/lib/types";
import { formatNumber } from "@/lib/format";

function anyFlag(r: SummaryRow): boolean {
  return (
    r.has_commits_before_t0 ||
    r.has_bulk_commits ||
    r.has_large_initial_commit_after_t0 ||
    r.has_merge_commits
  );
}

const pill =
  "inline-flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 text-xs font-medium text-text-secondary";

// Aggregate stat pills, computed over all rows (not the filtered view).
export function HeaderStats({ rows }: { rows: SummaryRow[] }) {
  const total = rows.length;
  const flagged = rows.filter(anyFlag).length;
  const clean = total - flagged;
  const commits = rows.reduce((sum, r) => sum + r.total_commits, 0);
  const loc = rows.reduce((sum, r) => sum + r.total_loc_added + r.total_loc_deleted, 0);

  return (
    <div className="hidden items-center gap-2 md:flex">
      <span className={pill}>
        <span className="font-mono font-semibold text-foreground">{total}</span> Submissions
      </span>
      <span className={pill}>
        <span className="font-mono font-semibold text-danger">{flagged}</span> Flagged
      </span>
      <span className={pill}>
        <span className="font-mono font-semibold text-ok">{clean}</span> Clean
      </span>
      <span className="mx-1 h-5 w-px bg-border" />
      <span className={pill}>
        <span className="font-mono font-semibold text-foreground">{formatNumber(commits)}</span> Commits
      </span>
      <span className={pill}>
        <span className="font-mono font-semibold text-loc">{formatNumber(loc)}</span> LoC
      </span>
    </div>
  );
}
