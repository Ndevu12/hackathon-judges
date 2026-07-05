import type { Commit } from "@/lib/types";
import { FlagBadge } from "./flag-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const HEADERS = ["#", "Time", "+", "−", "Files", "Bulk", "<T0", ">T1", "Message"];

export function CommitsTable({ commits }: { commits: Commit[] }) {
  if (!commits.length) {
    return (
      <div className="py-5 text-center text-sm text-muted-foreground">
        No commits data available
      </div>
    );
  }
  return (
    <div className="max-h-[300px] overflow-auto rounded-lg border border-border-subtle">
      <Table className="text-xs">
        <TableHeader>
          <TableRow>
            {HEADERS.map((h) => (
              <TableHead
                key={h}
                className="sticky top-0 z-10 h-8 bg-bg-subtle px-2.5 text-[0.6rem] tracking-wide text-muted-foreground uppercase"
              >
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {commits.map((c) => (
            <TableRow key={c.sha}>
              <TableCell className="px-2.5 py-2 font-mono">{c.seq_index}</TableCell>
              <TableCell className="px-2.5 py-2 text-[0.7rem] whitespace-nowrap text-muted-foreground">
                {c.author_time_iso}
              </TableCell>
              <TableCell className="px-2.5 py-2 font-mono text-ok">+{c.insertions}</TableCell>
              <TableCell className="px-2.5 py-2 font-mono text-danger">−{c.deletions}</TableCell>
              <TableCell className="px-2.5 py-2 font-mono">{c.files_changed}</TableCell>
              <TableCell className="px-2.5 py-2 text-center">
                <FlagBadge value={c.flag_bulk_commit} />
              </TableCell>
              <TableCell className="px-2.5 py-2 text-center">
                <FlagBadge value={c.is_before_t0} />
              </TableCell>
              <TableCell className="px-2.5 py-2 text-center">
                <FlagBadge value={c.is_after_t1} />
              </TableCell>
              <TableCell
                className="max-w-[180px] truncate px-2.5 py-2"
                title={c.subject}
              >
                {c.subject}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
