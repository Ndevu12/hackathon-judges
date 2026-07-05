"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { SortMode } from "./dashboard";

export type FilterKey = "pre" | "bulk" | "merge";

interface Props {
  filters: Record<FilterKey, boolean>;
  onFilter: (key: FilterKey, value: boolean) => void;
  sort: SortMode;
  onSort: (sort: SortMode) => void;
}

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "pre", label: "Pre-T0" },
  { key: "bulk", label: "Bulk" },
  { key: "merge", label: "Merge" },
];

export function FiltersBar({ filters, onFilter, sort, onSort }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {FILTERS.map(({ key, label }) => (
        <Label
          key={key}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-panel px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-primary hover:text-foreground"
        >
          <Checkbox
            checked={filters[key]}
            onCheckedChange={(checked) => onFilter(key, checked === true)}
          />
          {label}
        </Label>
      ))}
      <div className="flex items-center gap-2 rounded-lg border border-border bg-panel px-2.5 py-1.5 text-xs text-text-secondary">
        <span>Sort by</span>
        <select
          aria-label="Sort submissions"
          value={sort}
          onChange={(e) => onSort(e.target.value as SortMode)}
          className="rounded-md border border-border bg-bg-subtle px-2 py-1 text-xs text-foreground outline-none focus-visible:border-primary"
        >
          <option value="default">Default</option>
          <option value="commits">Commits</option>
          <option value="team">Team A–Z</option>
        </select>
      </div>
    </div>
  );
}
