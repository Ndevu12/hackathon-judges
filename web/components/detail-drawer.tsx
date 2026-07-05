"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Card } from "@/components/ui/card";
import type { AiAnalysis, RepoDetail, SubmissionInfo } from "@/lib/types";
import { cn } from "@/lib/utils";
import { verdictDisplay } from "@/lib/verdict";
import { CommitsTable } from "./commits-table";

interface Props {
  detail: RepoDetail | null;
  submission: SubmissionInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const sectionTitle =
  "mb-3 text-[0.7rem] font-semibold tracking-wide text-muted-foreground uppercase";

function MetricCard({ title, data }: { title: string; data: unknown }) {
  return (
    <Card className="gap-2 rounded-lg bg-bg-subtle p-3 ring-border-subtle">
      <div className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">{title}</div>
      <pre className="max-h-[120px] overflow-auto font-mono text-[0.7rem] leading-relaxed break-words whitespace-pre-wrap text-text-secondary">
        {JSON.stringify(data ?? {}, null, 2)}
      </pre>
    </Card>
  );
}

function AiSection({ ai }: { ai: AiAnalysis | null }) {
  if (!ai) {
    return (
      <p className="rounded-lg border border-border-subtle bg-bg-subtle p-4 text-sm text-muted-foreground">
        No AI analysis available for this submission.
      </p>
    );
  }
  const verdict = verdictDisplay(ai);
  const toneClass =
    verdict.tone === "authentic"
      ? "bg-ok/10 text-ok"
      : verdict.tone === "suspicious"
        ? "bg-danger/10 text-danger"
        : "bg-warn/10 text-warn";
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-subtle p-4 text-sm text-text-secondary">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={cn("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[0.8rem] font-semibold", toneClass)}>
          {verdict.icon} {verdict.label}
        </span>
        <span className="text-xs text-muted-foreground">confidence: {ai.confidence}</span>
      </div>
      {ai.summary && <p className="leading-relaxed text-foreground">{ai.summary}</p>}
      {ai.observations.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 leading-relaxed">
          {ai.observations.map((obs, i) => (
            <li key={i}>{obs}</li>
          ))}
        </ul>
      )}
      {ai.red_flags.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[0.7rem] font-semibold tracking-wide text-danger uppercase">Red flags</div>
          <ul className="list-disc space-y-1 pl-5 text-danger">
            {ai.red_flags.map((flag, i) => (
              <li key={i}>{flag}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TeamSection({ submission }: { submission: SubmissionInfo | null }) {
  if (!submission) {
    return (
      <div className="rounded-lg border border-border bg-bg-subtle p-3 text-sm text-muted-foreground">
        No submission info
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-border bg-bg-subtle p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-foreground">{submission.teamName || "—"}</span>
        <a
          href={submission.githubUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full border border-border bg-panel px-2.5 py-0.5 text-xs text-text-secondary hover:border-primary hover:text-primary"
        >
          GitHub ↗
        </a>
        {submission.liveUrl && (
          <a
            href={submission.liveUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-primary/40 bg-ok/10 px-2.5 py-0.5 text-xs text-primary hover:underline"
          >
            Live ↗
          </a>
        )}
      </div>
      {submission.members.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {submission.members.map((m, i) => (
            <li key={i} className="flex flex-wrap items-baseline justify-between gap-x-3 rounded-md border border-border bg-panel px-2.5 py-1.5">
              <span className="text-sm text-foreground">{m.name || "—"}</span>
              {m.email && <span className="font-mono text-[0.72rem] text-muted-foreground">{m.email}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-muted-foreground">No members listed</div>
      )}
    </div>
  );
}

export function DetailDrawer({ detail, submission, open, onOpenChange }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 border-border bg-panel p-0 sm:max-w-[600px]"
      >
        <SheetHeader className="border-b border-border bg-bg-subtle">
          <SheetTitle className="font-mono text-sm">
            {submission?.teamName || detail?.repoId || "Repository Details"}
          </SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-5">
          {detail && (
            <div className="flex flex-col gap-6">
              <section>
                <h3 className={sectionTitle}>Team</h3>
                <TeamSection submission={submission} />
              </section>
              <section>
                <h3 className={sectionTitle}>AI Analysis</h3>
                <AiSection ai={detail.ai} />
              </section>
              <div className="grid grid-cols-3 gap-3">
                <MetricCard title="Summary" data={detail.metrics?.summary} />
                <MetricCard title="Flags" data={detail.metrics?.flags} />
                <MetricCard title="Time Distribution" data={detail.metrics?.time_distribution} />
              </div>
              <section>
                <h3 className={cn(sectionTitle, "flex items-center gap-2")}>
                  Commits <span className="font-mono text-text-secondary">({detail.commitsTotal})</span>
                </h3>
                <CommitsTable commits={detail.commits} />
              </section>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
