"use client";

import { useMemo, useState } from "react";
import type { DashboardData, SubmissionInfo } from "@/lib/types";
import { HeaderStats } from "./header-stats";
import { FiltersBar, type FilterKey } from "./filters-bar";
import { SubmissionsTable } from "./submissions-table";
import { DetailDrawer } from "./detail-drawer";

export type SortMode = "default" | "commits" | "team";

export function Dashboard({ data }: { data: DashboardData }) {
  const [filters, setFilters] = useState<Record<FilterKey, boolean>>({
    pre: false,
    bulk: false,
    merge: false,
  });
  const [sort, setSort] = useState<SortMode>("default");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const submissionFor = (repoId: string): SubmissionInfo | null =>
    data.submissions[repoId] ?? null;
  const aiFor = (repoId: string) => data.details[repoId]?.aiText ?? null;

  const visibleRows = useMemo(() => {
    const rows = data.rows.filter((r) => {
      if (filters.pre && !r.has_commits_before_t0) return false;
      if (filters.bulk && !r.has_bulk_commits) return false;
      if (filters.merge && !r.has_merge_commits) return false;
      return true;
    });
    if (sort === "commits") {
      return [...rows].sort((a, b) => b.total_commits - a.total_commits);
    }
    if (sort === "team") {
      const name = (id: string) => data.submissions[id]?.teamName || id;
      return [...rows].sort((a, b) => name(a.repo_id).localeCompare(name(b.repo_id)));
    }
    return rows;
  }, [data.rows, data.submissions, filters, sort]);

  const selectRow = (repoId: string) => {
    setSelectedId(repoId);
    setOpen(true);
  };
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setSelectedId(null);
  };

  const selectedDetail = selectedId ? data.details[selectedId] ?? null : null;
  const selectedSubmission = selectedId ? data.submissions[selectedId] ?? null : null;

  return (
    <div className="relative z-10 min-h-screen">
      <header className="sticky top-0 z-40 flex items-center justify-between gap-4 border-b border-border bg-background/90 px-6 py-3.5 backdrop-blur-xl">
        <div className="bg-gradient-to-br from-primary to-[#00b4d8] bg-clip-text text-lg font-bold tracking-tight text-transparent">
          Hackathon Analyzer
        </div>
        <div className="flex items-center gap-5">
          <HeaderStats rows={data.rows} />
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" />
            {data.source === "empty" ? "No data" : "Live Dashboard"}
          </div>
        </div>
      </header>

      <main className="p-5">
        <section className="overflow-hidden rounded-xl border border-border bg-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-bg-subtle px-5 py-3.5">
            <h2 className="text-[0.95rem] font-semibold text-foreground">Submissions</h2>
            <FiltersBar
              filters={filters}
              onFilter={(key, value) => setFilters((f) => ({ ...f, [key]: value }))}
              sort={sort}
              onSort={setSort}
            />
          </div>
          <SubmissionsTable
            rows={visibleRows}
            submissionFor={submissionFor}
            aiFor={aiFor}
            selectedId={selectedId}
            onSelect={selectRow}
          />
        </section>
      </main>

      <DetailDrawer
        detail={selectedDetail}
        submission={selectedSubmission}
        open={open}
        onOpenChange={handleOpenChange}
      />
    </div>
  );
}
