import { humanize } from "@/lib/format";

// Outcome / disposition states carry meaning — semantic colors, never pastel (SPEC §9.5).
const CLASS: Record<string, string> = {
  recovered: "bg-outcome-recovered text-white",
  partial: "bg-outcome-partial text-ink",
  failed: "bg-outcome-failed text-white",
  deferred: "bg-outcome-deferred text-white",
  suppressed: "bg-outcome-suppressed text-white",
  awaiting_review: "bg-outcome-review text-white",
  passed: "bg-sage/30 text-sage-deep",
  blocked: "bg-outcome-suppressed/25 text-ink",
};

export function Chip({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs ${
        CLASS[value] ?? "bg-surface-sunk text-ink-soft"
      } ${className}`}
    >
      {humanize(value)}
    </span>
  );
}
