import { parse } from "csv-parse/sync";

// RFC-4180 CSV parsing (quoted fields, embedded commas/newlines) to match the
// Python csv.DictReader semantics used to write these files.
export function parseCsv(text: string): Record<string, string>[] {
  if (!text || !text.trim()) return [];
  return parse(text, {
    columns: true,
    skip_empty_lines: true,
    relax_column_count: true,
    bom: true,
  }) as Record<string, string>[];
}
