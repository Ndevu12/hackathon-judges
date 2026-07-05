"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Card } from "@/components/ui/card";
import type { JudgeInfo, RepoDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { extractVerdict, splitAtVerdict } from "@/lib/verdict";
import { CommitsTable } from "./commits-table";

interface Props {
  detail: RepoDetail | null;
  judge: JudgeInfo | null;
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

function AiSection({ aiText }: { aiText: string | null }) {
  if (!aiText) {
    return (
      <p className="rounded-lg border border-border-subtle bg-bg-subtle p-4 text-sm text-muted-foreground">
        No AI analysis available for this submission.
      </p>
    );
  }
  const { head, verdict } = splitAtVerdict(aiText);
  const tone = extractVerdict(aiText).tone;
  const verdictClass =
    tone === "authentic"
      ? "bg-ok/10 text-ok"
      : tone === "neutral"
        ? "bg-warn/10 text-warn"
        : "bg-danger/10 text-danger";
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-subtle p-4 text-sm leading-relaxed whitespace-pre-wrap text-text-secondary">
      {head}
      {verdict && (
        <span className={cn("mt-3 inline-block rounded-md px-3 py-1.5 text-[0.8rem] font-semibold", verdictClass)}>
          {verdict}
        </span>
      )}
    </div>
  );
}

function JudgeSection({ info }: { info: JudgeInfo | null }) {
  if (!info || !info.responses?.length) {
    return (
      <div className="rounded-lg border border-border bg-bg-subtle p-3 text-sm text-muted-foreground">
        No judge responses
      </div>
    );
  }
  const avg = Number(info.average_score || 0).toFixed(1);
  return (
    <div className="rounded-lg border border-border bg-bg-subtle p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-full border border-primary bg-ok/10 px-2.5 py-1.5 text-sm font-semibold text-foreground">{avg}</span>
        <span className="text-sm text-muted-foreground">
          {info.responses.length} response{info.responses.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {info.responses.map((r, i) => (
          <div key={i} className="rounded-lg border border-border bg-panel p-2.5">
            <span className="inline-flex rounded-full border border-border bg-panel-hover px-2.5 py-1 text-sm font-semibold text-foreground">
              #{i + 1} • {r.score}
            </span>
            {r.thoughts && <div className="mt-1 text-sm leading-snug text-foreground">{r.thoughts}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

export function DetailDrawer({ detail, judge, open, onOpenChange }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 border-border bg-panel p-0 sm:max-w-[600px]"
      >
        <SheetHeader className="border-b border-border bg-bg-subtle">
          <SheetTitle className="font-mono text-sm">
            {detail?.repoId ?? "Repository Details"}
          </SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-5">
          {detail && (
            <div className="flex flex-col gap-6">
              <section>
                <h3 className={sectionTitle}>AI Analysis</h3>
                <AiSection aiText={detail.aiText} />
              </section>
              <section>
                <h3 className={sectionTitle}>Judge Responses</h3>
                <JudgeSection info={judge} />
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
