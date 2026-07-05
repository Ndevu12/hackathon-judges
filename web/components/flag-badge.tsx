import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Yes/No flag chip, matching the original .flag ok/danger styling.
export function FlagBadge({ value }: { value: boolean }) {
  return (
    <Badge
      className={cn(
        "rounded px-2 py-0.5 text-[0.65rem] font-semibold tracking-wide uppercase",
        value ? "bg-danger/10 text-danger" : "bg-ok/10 text-ok",
      )}
    >
      {value ? "Yes" : "No"}
    </Badge>
  );
}
