"use client";

import type { AiAnalysis, SubmissionInfo, SummaryRow } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatNumber } from "@/lib/format";
import { FlagBadge } from "./flag-badge";
import { VerdictBadge } from "./verdict-badge";
import { AIPreview } from "./ai-preview";

interface Props {
  rows: SummaryRow[];
  submissionFor: (repoId: string) => SubmissionInfo | null;
  aiFor: (repoId: string) => AiAnalysis | null;
  selectedId: string | null;
  onSelect: (repoId: string) => void;
}

const th =
  "sticky top-0 z-10 bg-bg-subtle text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase";

// Stop row-click (drawer) from firing when a link inside the row is clicked.
function stop(e: React.MouseEvent) {
  e.stopPropagation();
}

export function SubmissionsTable({ rows, submissionFor, aiFor, selectedId, onSelect }: Props) {
  return (
    <div className="max-h-[calc(100vh-160px)] overflow-auto">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className={cn(th, "min-w-[160px]")}>Team</TableHead>
            <TableHead className={cn(th, "min-w-[200px]")}>Repository</TableHead>
            <TableHead className={cn(th, "text-right")} title="Total number of commits in the repository">Commits</TableHead>
            <TableHead className={cn(th, "text-right")} title="Lines of code added across all commits">LOC+</TableHead>
            <TableHead className={cn(th, "text-right")} title="Lines of code deleted across all commits">LOC−</TableHead>
            <TableHead className={cn(th, "text-center")} title="Commits made before the hackathon start time (T0)">Pre-T0</TableHead>
            <TableHead className={cn(th, "text-center")} title="Contains bulk commits with unusually large changes">Bulk</TableHead>
            <TableHead className={cn(th, "text-center")} title="Large initial commit after T0 (potential pre-work)">Init</TableHead>
            <TableHead className={cn(th, "text-center")} title="Contains merge commits (may indicate external collaboration)">Merge</TableHead>
            <TableHead className={cn(th, "text-center")} title="AI assessment of project authenticity">Assessment</TableHead>
            <TableHead className={cn(th, "min-w-[200px]")}>AI Summary</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={11}>
                <div className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                  <span className="text-2xl opacity-50">📭</span>
                  <span>No submissions match the current filters</span>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row) => {
              const ai = aiFor(row.repo_id);
              const sub = submissionFor(row.repo_id);
              const selected = row.repo_id === selectedId;
              return (
                <TableRow
                  key={row.repo_id}
                  onClick={() => onSelect(row.repo_id)}
                  className={cn(
                    "cursor-pointer",
                    selected &&
                      "bg-primary/10 shadow-[inset_3px_0_0_var(--primary)] hover:bg-primary/10",
                  )}
                >
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[0.85rem] font-semibold text-foreground">
                        {sub?.teamName || "—"}
                      </span>
                      {sub && sub.members.length > 0 && (
                        <span className="text-[0.7rem] text-muted-foreground">
                          {sub.members.length} member{sub.members.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-mono text-[0.8rem] text-foreground">{row.repo_id}</span>
                      <div className="flex items-center gap-2 text-[0.7rem]">
                        <a
                          href={sub?.githubUrl || row.repo}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={stop}
                          className="max-w-[220px] truncate text-muted-foreground hover:text-primary hover:underline"
                        >
                          {(sub?.githubUrl || row.repo).replace(/^https?:\/\//, "")}
                        </a>
                        {sub?.liveUrl && (
                          <a
                            href={sub.liveUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={stop}
                            className="shrink-0 text-primary hover:underline"
                          >
                            Live ↗
                          </a>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-[0.8rem]">{row.total_commits}</TableCell>
                  <TableCell className="text-right font-mono text-[0.8rem] text-ok">+{formatNumber(row.total_loc_added)}</TableCell>
                  <TableCell className="text-right font-mono text-[0.8rem] text-danger">−{formatNumber(row.total_loc_deleted)}</TableCell>
                  <TableCell className="text-center"><FlagBadge value={row.has_commits_before_t0} /></TableCell>
                  <TableCell className="text-center"><FlagBadge value={row.has_bulk_commits} /></TableCell>
                  <TableCell className="text-center"><FlagBadge value={row.has_large_initial_commit_after_t0} /></TableCell>
                  <TableCell className="text-center"><FlagBadge value={row.has_merge_commits} /></TableCell>
                  <TableCell className="text-center"><VerdictBadge ai={ai} /></TableCell>
                  <TableCell className="max-w-[320px] min-w-[200px] whitespace-normal"><AIPreview ai={ai} /></TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
